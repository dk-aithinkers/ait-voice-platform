#!/usr/bin/env python3
"""CDK entrypoint.

    cd infra
    python -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/python app.py            # synthesise, no AWS call
    npx cdk deploy --all               # needs credentials

Three stacks, and the split is deliberate. `PlatformStack` holds what must
survive a bad deploy — the database and the two buckets, one of them under
Object Lock. `ServiceStack` holds what is replaced on every release.
`CiStack` holds the role GitHub Actions assumes.

Two regions are configured because C-T1 makes per-region deployment a hard
constraint: no vendor serves US healthcare and India adequately, so the tenants
do not share a pipeline. Only US is enabled today, matching the US-first pilot
decision; India is present and commented so the shape is visible rather than
rediscovered.
"""

from __future__ import annotations

import os

import aws_cdk as cdk
from stacks.cicd import CiStack
from stacks.platform import PlatformStack
from stacks.service import ServiceStack

REPOSITORY = "dk-aithinkers/ait-voice-platform"

# Explicit outdir so `python app.py` synthesises verifiably without the Node
# CLI. Under `cdk deploy` the CLI sets CDK_OUTDIR and that wins.
app = cdk.App(outdir=os.environ.get("CDK_OUTDIR", "cdk.out"))
image_tag = app.node.try_get_context("imageTag") or os.environ.get("IMAGE_TAG", "dev")

us = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("AIT_AWS_REGION", "us-east-1"),
)

platform = PlatformStack(app, "AitVoice-Platform-US", region_label="us", env=us)

ServiceStack(
    app,
    "AitVoice-Service-US",
    vpc=platform.vpc,
    database=platform.database,
    db_secret=platform.db_secret,
    audit_bucket=platform.audit_bucket,
    content_bucket=platform.content_bucket,
    image_tag=image_tag,
    env=us,
)

CiStack(
    app,
    "AitVoice-Ci",
    repository=REPOSITORY,
    existing_provider_arn=app.node.try_get_context("githubOidcProviderArn"),
    env=us,
)

# India: blocked on D-04 (DLT registration, 1600-series numbering) for outbound,
# and on D-02 for Indic accuracy. Inbound would work today. Left here rather
# than deleted so the dual-region shape C-T1 requires stays visible.
#
# india = cdk.Environment(account=..., region="ap-south-1")
# PlatformStack(app, "AitVoice-Platform-IN", region_label="india", env=india)

app.synth()
