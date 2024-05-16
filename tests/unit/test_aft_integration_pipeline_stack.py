import aws_cdk as core
import aws_cdk.assertions as assertions

from aft_integration_pipeline.aft_integration_pipeline_stack import AftIntegrationPipelineStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aft_integration_pipeline/aft_integration_pipeline_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AftIntegrationPipelineStack(app, "aft-integration-pipeline")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
