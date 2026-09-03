"""The running service: ECS Fargate behind a load balancer, plus the migration task.

Replaceable by design. Everything stateful is in `PlatformStack`, so this stack
can be torn down and rebuilt without threatening a database or an audit bucket.

The IAM here is the part worth reading. The task role can write the audit
bucket and cannot delete from it — Object Lock already refuses, but a role that
cannot even ask is one less thing depending on a bucket setting being right.
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class ServiceStack(Stack):
    def __init__(  # noqa: PLR0913 - a stack wires things; each argument is one of them
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        database: rds.IDatabaseInstance,
        db_secret: secretsmanager.ISecret,
        audit_bucket: s3.IBucket,
        content_bucket: s3.IBucket,
        image_tag: str,
        **kw,  # noqa: ANN003
    ) -> None:
        super().__init__(scope, construct_id, **kw)

        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        # Application credentials, separate from the owner secret the migration
        # uses. `ait_app` is deliberately not a superuser: a superuser bypasses
        # row-level security unconditionally, so tenant isolation would be
        # switched on and enforcing nothing. `Database.connect()` refuses one.
        app_secret = secretsmanager.Secret(
            self,
            "AppDbSecret",
            description="ait_app credentials. Not a superuser — see docs/database.md.",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                # S106: this template carries a username. The password is the
                # part Secrets Manager generates, and it never appears in source
                # or in a synthesised template.
                secret_string_template='{"username":"ait_app"}',  # noqa: S106
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        log_group = logs.LogGroup(
            self,
            "ServiceLogs",
            retention=logs.RetentionDays.ONE_YEAR,
        )

        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="What a running container may touch.",
        )

        # Append and read. No delete, no retention manipulation, no governance
        # bypass — the bucket would refuse anyway, and a role that cannot ask is
        # one less dependency on a bucket setting staying correct.
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
                resources=[audit_bucket.bucket_arn, audit_bucket.arn_for_objects("*")],
            )
        )
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                actions=[
                    "s3:DeleteObject",
                    "s3:DeleteObjectVersion",
                    "s3:PutObjectRetention",
                    "s3:BypassGovernanceRetention",
                    "s3:PutBucketObjectLockConfiguration",
                ],
                resources=[audit_bucket.bucket_arn, audit_bucket.arn_for_objects("*")],
            )
        )
        # Content is the erasable half; deleting from it is the point.
        content_bucket.grant_read_write(task_role)
        content_bucket.grant_delete(task_role)
        app_secret.grant_read(task_role)

        image = ecs.ContainerImage.from_asset("..", file="Dockerfile", exclude=["infra/cdk.out"])

        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Api",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=2,  # Two AZs, so a task loss is not an outage.
            public_load_balancer=True,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=image,
                container_port=8000,
                task_role=task_role,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="api", log_group=log_group),
                environment={
                    "AIT_DB_HOST": database.db_instance_endpoint_address,
                    "AIT_DB_PORT": database.db_instance_endpoint_port,
                    "AIT_DB_NAME": "aitvoice",
                    "AIT_DB_USER": "ait_app",
                    "AIT_AUDIT_BUCKET": audit_bucket.bucket_name,
                    "AIT_CONTENT_BUCKET": content_bucket.bucket_name,
                    "AIT_LOG_LEVEL": "INFO",
                    # Blank, deliberately. The filesystem audit log is
                    # per-task and forks the hash chain across containers; a
                    # path here would silently re-enable it.
                    "AIT_AUDIT_ROOT": "",
                    "AIT_CONTENT_ROOT": "",
                    "IMAGE_TAG": image_tag,
                },
                secrets={
                    "AIT_DB_PASSWORD": ecs.Secret.from_secrets_manager(app_secret, "password"),
                },
            ),
        )

        self.service.target_group.configure_health_check(
            path="/api/health",
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
            interval=Duration.seconds(15),
            timeout=Duration.seconds(5),
        )
        # Long enough for in-flight requests, short enough that a deploy is not
        # an event. Calls are the long-lived thing here, and they are not on
        # this listener.
        self.service.target_group.set_attribute("deregistration_delay.timeout_seconds", "30")

        CfnOutput(
            self, "ServiceUrl", value=f"http://{self.service.load_balancer.load_balancer_dns_name}"
        )
        CfnOutput(self, "AppDbSecretArn", value=app_secret.secret_arn)
        CfnOutput(
            self,
            "TlsWarning",
            value=(
                "HTTP only: no domain or ACM certificate is configured yet. "
                "PHI must not traverse this listener until HTTPS is in front of it."
            ),
        )
