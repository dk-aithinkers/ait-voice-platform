"""The role CI assumes, federated through GitHub's OIDC provider.

`team.md`: "CI authenticates to AWS via OIDC federation to a scoped role, not
long-lived access keys stored as CI secrets." A stored access key is a
credential that lives until someone remembers to rotate it, in a place that
prints its own logs; a federated token lasts minutes and is bound to a workflow
run.

The trust policy is where this is either a control or a decoration. The `sub`
condition binds the role to *this repository*, so a token minted by any other
repo on GitHub — which is to say, by anyone — cannot assume it.
"""

from __future__ import annotations

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com"


class CiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repository: str,
        existing_provider_arn: str | None = None,
        **kw,  # noqa: ANN003
    ) -> None:
        super().__init__(scope, construct_id, **kw)

        # An account may only have one provider for a given issuer, so adopt an
        # existing one when told to rather than failing the whole deploy on a
        # duplicate.
        if existing_provider_arn:
            provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, "GithubOidc", existing_provider_arn
            )
        else:
            provider = iam.OpenIdConnectProvider(
                self,
                "GithubOidc",
                url=GITHUB_OIDC_URL,
                client_ids=["sts.amazonaws.com"],
            )

        self.deploy_role = iam.Role(
            self,
            "DeployRole",
            assumed_by=iam.WebIdentityPrincipal(
                provider.open_id_connect_provider_arn,
                {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    },
                    # Bound to one repository. Without this the role trusts
                    # every workflow on GitHub, which is not a smaller mistake
                    # than a leaked access key.
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": f"repo:{repository}:*"
                    },
                },
            ),
            description=f"Assumed by GitHub Actions in {repository}",
            max_session_duration=__import__("aws_cdk").Duration.hours(1),
        )

        # Broad for now, and flagged rather than pretended otherwise: CDK
        # deploys need wide permissions, and narrowing them properly means
        # enumerating what each stack touches. That is worth doing before this
        # role can deploy to production — recorded in docs/deploying.md.
        self.deploy_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("PowerUserAccess")
        )
        self.deploy_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:*Role*", "iam:*Policy*", "iam:PassRole"],
                resources=["*"],
            )
        )

        CfnOutput(self, "DeployRoleArn", value=self.deploy_role.role_arn)
        CfnOutput(
            self,
            "PermissionsWarning",
            value=(
                "PowerUserAccess plus IAM: sufficient for CDK, wider than a "
                "production deploy role should be. Narrow before first "
                "production use — docs/deploying.md."
            ),
        )
