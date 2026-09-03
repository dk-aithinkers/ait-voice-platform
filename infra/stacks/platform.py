"""Stateful infrastructure: the network, the database, and the two buckets.

Separated from the service stack because these outlive it. A task definition is
replaced on every deploy; a database and an audit bucket under Object Lock are
things you must not be able to destroy by editing a container image tag.

The two buckets are the point of this file. `project.md`:

    The two log classes carry different retention policies and are enforced as
    separate infrastructure (separate sinks, separate IaC-defined retention),
    not merely as a written convention, so the separation is machine-checkable
    rather than memorized.

C-R7 requires security logs retained a year. C-R8 requires personal data erased
once its purpose ends. Both hold only if they apply to disjoint data — so the
audit bucket is immutable and retained, the content bucket is erasable and
expires, and nothing writes call content to the first one.
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Duration, RemovalPolicy, SecretValue, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class PlatformStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, region_label: str, **kw) -> None:  # noqa: ANN003
        super().__init__(scope, construct_id, **kw)

        # -- network ------------------------------------------------------
        #
        # Two NAT gateways rather than one: a single NAT is a single AZ, and
        # NFR2.1's 99.5% is a monthly figure that one AZ outage can spend in an
        # afternoon. The database sits in isolated subnets with no route out at
        # all — nothing in it should ever originate a connection.
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="app", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="data", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24
                ),
            ],
        )

        # -- database -----------------------------------------------------
        #
        # The password is generated into Secrets Manager and never appears in a
        # template, a task definition or an environment variable in the console.
        # `db/migrations/001_initial.sql` creates `ait_app` with a placeholder
        # password that a real environment replaces from here — see
        # docs/database.md.
        self.db_secret = secretsmanager.Secret(
            self,
            "DbOwnerSecret",
            description="Postgres owner credentials. Migrations only; the app connects as ait_app.",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                # S106: this template carries a username. The password is the
                # part Secrets Manager generates, and it never appears in source
                # or in a synthesised template.
                secret_string_template='{"username":"postgres"}',  # noqa: S106
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        self.database = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                # A concrete minor, not bare "17": RDS refuses a major-only
                # version for new instances, and cfn-lint (W3691) catches that
                # before a deploy does. Matches the 17.x the test suite and the
                # CI service container already run against.
                version=rds.PostgresEngineVersion.VER_17_6
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MEDIUM
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            credentials=rds.Credentials.from_secret(self.db_secret),
            database_name="aitvoice",
            multi_az=True,
            # HIPAA-eligible only with encryption at rest, and the AWS BAA
            # covers RDS only when it is on. Not a default worth inheriting.
            storage_encrypted=True,
            backup_retention=Duration.days(35),
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN,
            publicly_accessible=False,
            auto_minor_version_upgrade=True,
        )

        # Ingress scoped to the app subnets rather than to the service's
        # security group. An SG-to-SG rule would be tighter, but it has to be
        # written into *this* stack's security group by the service stack —
        # which already depends on this one, so CloudFormation rejects the
        # cycle. A CIDR confined to private subnets with no inbound route from
        # the internet is the honest trade, and it keeps the database's own
        # reachability described in one file.
        for subnet in self.vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        ).subnets:
            self.database.connections.allow_default_port_from(
                ec2.Peer.ipv4(subnet.ipv4_cidr_block),
                f"app subnet {subnet.availability_zone}",
            )

        # -- voice service secrets -----------------------------------------
        #
        # Generated here rather than in the service stack because a rotation
        # that invalidated every in-flight call token on each deploy would be a
        # dropped call, and the service stack is the one that gets replaced.
        self.relay_secret = secretsmanager.Secret(
            self,
            "RelayTokenSecret",
            description=(
                "Signs the token authorising a ConversationRelay socket. Twilio "
                "sends no credential on that connection, so this is the only "
                "thing standing between a public WebSocket and a tenant context."
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=48, exclude_punctuation=True
            ),
        )

        # A vendor credential, so it cannot be generated — it is created empty
        # and filled from the Twilio console. The voice service refuses to start
        # without it, which is what stops an empty placeholder reaching
        # production quietly: with no token every webhook signature fails to
        # validate, and a service that cannot tell Twilio from anyone else must
        # not answer.
        self.twilio_auth_token = secretsmanager.Secret(
            self,
            "TwilioAuthToken",
            description="Twilio account auth token. Set manually; validates the webhook signature.",
            secret_string_value=SecretValue.unsafe_plain_text("REPLACE-ME"),
        )

        # -- the audit bucket: immutable, retained -------------------------
        #
        # Object Lock in COMPLIANCE mode. Not GOVERNANCE: governance mode can be
        # bypassed by a principal holding s3:BypassGovernanceRetention, which
        # makes the retention a policy rather than a property. Compliance mode
        # cannot be bypassed by anyone, including the account root.
        #
        # What it does and does not cover, verified against a real
        # implementation rather than assumed: a versioned delete is refused, so
        # nothing written can be destroyed. An UNVERSIONED delete is accepted
        # and writes a delete marker, and a PutObject on an existing key adds a
        # version — neither destroys anything, but both change what a naive
        # reader sees. S3AuditLog reads the oldest version of each key for that
        # reason, and the task role's explicit Deny in service.py is what stops
        # either being attempted.
        #
        # OBJECT LOCK CANNOT BE ENABLED AFTER CREATION. If this bucket is ever
        # replaced, the replacement must be created with it on from the start.
        self.audit_bucket = s3.Bucket(
            self,
            "AuditBucket",
            object_lock_enabled=True,
            object_lock_default_retention=s3.ObjectLockRetention.compliance(
                Duration.days(365)  # C-R7: security logs, at least one year.
            ),
            versioned=True,  # Required by Object Lock.
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # -- the content bucket: erasable, expiring -------------------------
        #
        # The other half of the C-R7 / C-R8 resolution. Transcripts and
        # recordings live here so DPDP erasure can delete them without touching
        # the security record. Deliberately NOT under Object Lock: an erasure
        # request that cannot be honoured is a compliance failure in the other
        # direction.
        self.content_bucket = s3.Bucket(
            self,
            "ContentBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=False,  # A version nobody can delete would defeat erasure.
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-content",
                    enabled=True,
                    # A backstop, not the erasure mechanism: purpose-fulfilled
                    # deletion is the application's job and happens sooner. This
                    # is what catches anything the application forgot.
                    expiration=Duration.days(90),
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,
        )

        for name, value in {
            "VpcId": self.vpc.vpc_id,
            "DbEndpoint": self.database.db_instance_endpoint_address,
            "DbSecretArn": self.db_secret.secret_arn,
            "AuditBucketName": self.audit_bucket.bucket_name,
            "ContentBucketName": self.content_bucket.bucket_name,
            "Region": region_label,
            "RelaySecretArn": self.relay_secret.secret_arn,
            "TwilioAuthTokenArn": self.twilio_auth_token.secret_arn,
        }.items():
            CfnOutput(self, name, value=value)
