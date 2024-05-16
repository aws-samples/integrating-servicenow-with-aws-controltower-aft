#!/usr/bin/env python3
import os
import aws_cdk as cdk
import cdk_nag
from aws_cdk import (
    Aspects
)

from aft_integration_pipeline.aft_integration_pipeline_stack import AftIntegrationPipelineStack


app = cdk.App()
AftIntegrationPipelineStack(app, "AftIntegrationPipelineStack",env=cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"],region=os.environ["CDK_DEFAULT_REGION"]))
Aspects.of(app).add(cdk_nag.AwsSolutionsChecks())
app.synth()
