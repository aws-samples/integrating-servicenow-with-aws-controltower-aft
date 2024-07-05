from aws_cdk import (
    Stack,
    aws_codecommit as codecommit,
    aws_codebuild as codebuild,
    aws_lambda as lambda_func,
    aws_lambda_python_alpha as lambda_alpha,
    aws_iam as iam,
    aws_sns as sns,
    aws_apigateway as apigateway,
    aws_ssm as ssm, 
    aws_secretsmanager as secretsmanager,
    CustomResource as CustomResource,
    custom_resources as customeresource,
    aws_logs as logs,
    Duration as Duration,
    Aws
)
import cdk_nag
import aws_cdk
import json
from constructs import Construct

class AftIntegrationPipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        
        # Account and Region Configuration
        current_account_id=aws_cdk.Aws.ACCOUNT_ID
        current_region=aws_cdk.Aws.REGION
        aft_account_repo=self.node.try_get_context("aft_account_request_repository")
        api_key_length = self.node.try_get_context("api_key_length")
        
        # Create Secrets Manager for SNOW User and Password 
        snow_secret = secretsmanager.Secret(self, "snowsecret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"username": "admin"}),
                generate_string_key="password",
                exclude_characters="/@"
            )
        )
        # Nag supresssion for Key Rotation 
        cdk_nag.NagSuppressions.add_resource_suppressions(snow_secret, [
        {
            "id": 'AwsSolutions-SMG4',
            "reason": 'The Secrets manager is leveraged to store service now secrets which is an external component and should not be automatically rotated.'
        },
        ])

        # Create CodeCommit Repository that will hold the Integration script for the solution -> This should be created later in new AFT account 
        integration_pipeline_repo = codecommit.Repository(self, "aft_integration_pipeline", repository_name="aft_integration_pipeline")
        
        pipeline_codecommit_repo = codecommit.Repository.from_repository_name(self, "aft_integration_pipeline_name", repository_name=integration_pipeline_repo.repository_name)
        
        # Create a CodeBuild project
        codebuild_project=codebuild.Project(
            self, "aft-integration-build",
                project_name="aft-integration-build",
                source=codebuild.Source.code_commit(repository=pipeline_codecommit_repo),
                # secondary_sources=[codebuild.Source.code_commit(repository=aft_codecommit_repo, identifier="aftrequest")], # This is not required 
                build_spec=codebuild.BuildSpec.from_object({
                    "version": "0.2",
                    "phases": {
                        "pre_build": {
                            "commands": [
                                # Install HTTPS(GRC)
                                "pip install git-remote-codecommit",
                                # The AFT Repository 
                                "AFT_REPO_DIR=$(find /codebuild/output -type d -name $AFT_ACCOUNT_REPO)",
                                "echo $AFT_REPO_DIR",
                                "echo $CODEBUILD_SRC_DIR",
                                # Setting up Git credentials
                                "git config --global user.email $GIT_COMMITTER_EMAIL",
                                "git config --global user.name $GIT_COMMITTER_NAME"
                              ]
                        },
                        "build": {
                            "commands": [
                                "#!/bin/bash",
                                "echo copy the json input payload into the input file snow_input.json",
                                "ls -lrt",
                                "echo $JSON_PAYLOAD > ./snow_input.json",
                                "echo $JSON_PAYLOAD",
                                "ls -lrt",
                                "echo Running generate_tfvars_payload.py script",
                                "python3 generate_tfvars_payload.py",
                                "ls -lrt",
                                "dir=$AFT_REPO_DIR/terraform",
                                "if [ $(ls $dir/*.tf 1> /dev/null 2>&1) ]; then cp -r $dir/*.tf .; else echo No Terraform files found in $dir; fi",
                                "if [ $(ls $dir/*.auto.tfvars.json 1> /dev/null 2>&1) ]; then cp -r $dir/*.auto.tfvars.json .; else echo No Terraform TFVARS files found in $dir; fi",
                                "ls -lrt",
                                "echo Running generate_tfvars.py script",
                                "python3 generate_tfvars.py",
                                "ls -lrt",
                                "cd /codebuild/output",
                                "git clone codecommit::$REGION://$AFT_ACCOUNT_REPO aft-account-request",
                                "cd aft-account-request/terraform",
                                "ls -lrt",
                                "cp -r $CODEBUILD_SRC_DIR/*.tf .",
                                "cp -r $CODEBUILD_SRC_DIR/*.auto.tfvars.json .",
                                "ls -lrt",
                                "git add .",
                                "git commit -m \"Pushing the account files to AFT Account Request Repository throught Integration automation\"",
                                "git push"
                            ]
                        }
                    }
                }),
                environment=codebuild.BuildEnvironment(
                    build_image=codebuild.LinuxBuildImage.STANDARD_5_0,
                    # Define environment variables
                   environment_variables={
                    "JSON_PAYLOAD": codebuild.BuildEnvironmentVariable(value="some value"),
                    "REGION": codebuild.BuildEnvironmentVariable(value=self.region),
                    "GIT_COMMITTER_EMAIL" : codebuild.BuildEnvironmentVariable(value=self.node.try_get_context("aft_account_request_committer_email")),
                    "GIT_COMMITTER_NAME" : codebuild.BuildEnvironmentVariable(value=self.node.try_get_context("aft_account_request_committer_name")),
                    "AFT_ACCOUNT_REPO": codebuild.BuildEnvironmentVariable(value=aft_account_repo)
                  }
                )
        )

        # Nag supresssion for KMS key to use AWS Managed instead of Customer managed 
        cdk_nag.NagSuppressions.add_resource_suppressions(codebuild_project, [
        {
            "id": 'AwsSolutions-CB4',
            "reason": 'The codebuild artifact uses AWS Managed KMS key aws/s3 for encryption.'
        },
        ])

        codebuild_project.add_to_role_policy(iam.PolicyStatement(actions=["codecommit:GitPush","codecommit:GitPull"], resources=[f"arn:aws:codecommit:{current_region}:{current_account_id}:{aft_account_repo}"]))

        # Nag supresssion for Codebuild service role as wildcard is specific to code build project.  
        cdk_nag.NagSuppressions.add_resource_suppressions(codebuild_project, [
        {
            "id": 'AwsSolutions-IAM5',
            "reason": 'The Wildcard is spefic to the project arn arn:aws:logs:<region>:<account>:log-group:/aws/codebuild/aft-integration-build:*.'
        },
        ],
        apply_to_children=True
        )

        # IAM Role for AFT SNOW integration Lambda function
        snow_lambda_role = iam.Role(self, "SnowAFTLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant permissions to the Lambda function to get SSM Parameter Store for snow Creds and Codepipeline
        snow_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=[snow_secret.secret_arn]
        ))

        snow_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["codepipeline:ListPipelineExecutions"],
            resources=["*"]
        ))

        # Layer for the Lambda Function 
        lambda_layer = lambda_alpha.PythonLayerVersion(
            self, "aft-snow-integration-layer",
            entry="./lambda/layer",
            compatible_runtimes=[lambda_func.Runtime.PYTHON_3_12],
            layer_version_name="aft-snow-integration-layer")
        
        # Define the Lambda function to return Status to the snow Tool
        lambda_function = lambda_func.Function(
            self, "aft-snow-integration-function",
            runtime=lambda_func.Runtime.PYTHON_3_12,
            function_name="aft-snow-integration-function",
            handler="index.lambda_handler",
            role= snow_lambda_role,
            tracing = lambda_func.Tracing.ACTIVE,
            code=lambda_func.Code.from_asset("./lambda/aft_snow_integration"),
            layers=[lambda_layer],
            timeout=Duration.seconds(300),
            environment = {
                "api_endpoint_url": self.node.try_get_context("snow_api_endpoint_url"),
                "snow_secret_arn": snow_secret.secret_arn
            }
        )

        # Grant permission to the Lambd function to create Cloudwatch Log group
        snow_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/aft-snow-integration-function",
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/aft-snow-integration-function:log-stream:*"
            ]
        ))

        # Nag supresssion for Lambda service role as wildcard is specific to function.  
        cdk_nag.NagSuppressions.add_resource_suppressions(snow_lambda_role, [
        {
            "id": 'AwsSolutions-IAM5',
            "reason": 'The Wildcard is specific to Arn of Lambda log group'
        },
        ],
        apply_to_children=True
        )
        
        # AFT Notification subscription
        aft_notification_topic = sns.Topic.from_topic_arn(self, "aft-notification",topic_arn=f"arn:aws:sns:{current_region}:{current_account_id}:aft-notifications")

        sns.Subscription(self, "Subscription",
                      topic=aft_notification_topic,
                      endpoint=lambda_function.function_arn,
                      protocol=sns.SubscriptionProtocol.LAMBDA)
        
        # Grant Permission for SNS topic to invoke the Lambda function
        lambda_function.add_permission(
            "sns_permission",
            action="lambda:InvokeFunction",
            principal=iam.ServicePrincipal("sns.amazonaws.com"),
            source_arn=f"arn:aws:sns:{current_region}:{current_account_id}:aft-notifications")
        
        # Lambda authorizer for the API Gateway and its configuration 

        api_key_name = ssm.StringParameter(self, 'api_key_parameter',
            parameter_name= '/snow/aft-integration/api-token',
            string_value= 'default',
            description= 'The SSM parameter name for the API gateway API key.',
        )

         # IAM Role for Authorizer Lambda function
        authorizer_lambda_function_role = iam.Role(self, "AuthorizerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant permissions to the Lambda function to get SSM Parameter Store
        authorizer_lambda_function_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[api_key_name.parameter_arn]
        ))

        authorizer_lambda_function = lambda_func.Function(
            self, "api-lambda-authorizerfunction",
            description= 'AWS Lambda authorizer tied to Rest API',
            runtime=lambda_func.Runtime.PYTHON_3_12,
            role= authorizer_lambda_function_role,
            function_name="api-lambda-authorizerfunction",
            handler="index.lambda_handler",
            code=lambda_func.Code.from_asset("./lambda/lambda_authorizer"),
            timeout=Duration.seconds(300),
            tracing = lambda_func.Tracing.ACTIVE,
            environment = {
                "PARAMETER_NAME": api_key_name.parameter_name
            }
        )

        # Grant permission to the Lambda function to create Cloudwatch Log group
        authorizer_lambda_function_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/api-lambda-authorizerfunction",
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/api-lambda-authorizerfunction:log-stream:*"
            ]
        ))

        # Nag supresssion for Lambda service role as wildcard is specific to function.  
        cdk_nag.NagSuppressions.add_resource_suppressions(authorizer_lambda_function_role, [
        {
            "id": 'AwsSolutions-IAM5',
            "reason": 'The Wildcard is specific to Arn of Lambda log group'
        },
        ],
        apply_to_children=True
        )

        # IAM Role for Authorizer Lambda function
        custom_resource_lambda_function_role = iam.Role(self, "CustomResourceLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant permissions to the Lambda function to Put, Delete SSM Parameter Store
        custom_resource_lambda_function_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:PutParameter", "ssm:DeleteParameter", "ssm:DeleteParameters"],
            resources=[api_key_name.parameter_arn]
        ))

        api_key_generation_custom_resource = lambda_func.Function(
            self, "api-key-generation-custom-resource",
            runtime=lambda_func.Runtime.PYTHON_3_12,
            function_name="api-key-generation-custom-resource",
            role= custom_resource_lambda_function_role,
            handler="index.lambda_handler",
            code=lambda_func.Code.from_asset("./lambda/custom_resource"),
            timeout=Duration.seconds(300),
            tracing = lambda_func.Tracing.ACTIVE,
            environment = {
                "PARAMETER_NAME": api_key_name.parameter_name
            }
        )
        
        # Grant permission to the Lambda function to create Cloudwatch Log group
        custom_resource_lambda_function_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/api-key-generation-custom-resource",
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/api-key-generation-custom-resource:log-stream:*"
            ]
        ))

        # Nag supresssion for Lambda service role as wildcard is specific to function.  
        cdk_nag.NagSuppressions.add_resource_suppressions(custom_resource_lambda_function_role, [
        {
            "id": 'AwsSolutions-IAM5',
            "reason": 'The Wildcard is specific to Arn of Lambda log group'
        },
        ],
        apply_to_children=True
        )

        api_key_provider = customeresource.Provider(self, "ApiKeyProvider",
            on_event_handler=api_key_generation_custom_resource
        )

        api_key_creation_cr = CustomResource(self, "ApiKeyGeneratorCR",
            resource_type="Custom::MyCustomResourceType",
            properties = {
                "ApiLength": api_key_length,
                "description": 'The custom Resource to create Api key and used by Lambda and authorizer.',
            },
            service_token=api_key_provider.service_token
        )

        # Nag supresssion for Lambda Runtime for NodeJS provisioned by CDK .  
        cdk_nag.NagSuppressions.add_resource_suppressions(api_key_provider, [
        {
            "id": 'AwsSolutions-L1',
            "reason": 'Custom Resource provider supports only Nodejs 18 version though 20 is the latest hence supressing'
        },
        ],
        apply_to_children=True
        )

        # Nag supresssion for Lambda Role provisioned by CDK . 
        cdk_nag.NagSuppressions.add_resource_suppressions(api_key_provider, [
        {
            "id": 'AwsSolutions-IAM4',
            "reason": 'Custom Resource provider provisions the role and associates the necessary policy'
        },
        ],
        apply_to_children=True
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(api_key_provider, [
        {
            "id": 'AwsSolutions-IAM5',
            "reason": 'Custom Resource provider provisions the role and associates the necessary policy'
        },
        ],
        apply_to_children=True
        )


        # API For snow Integration 
       
        lambda_authorizer = apigateway.TokenAuthorizer(self, "lambdaAuthorizer", handler=authorizer_lambda_function)

        api_access_log_group = logs.LogGroup(self, "APIAccessLogGroup",
            retention=logs.RetentionDays.ONE_DAY
        )

        api = apigateway.RestApi(self, "AFTCodeBuildApi",
            rest_api_name="AFTIntegrationApi",
            description="API for triggering AFT CodeBuild projects",
            cloud_watch_role = True, 
            deploy = True,
            deploy_options = apigateway.StageOptions(
                stage_name="dev",
                logging_level=apigateway.MethodLoggingLevel.INFO,
                access_log_destination=apigateway.LogGroupLogDestination(api_access_log_group),
                data_trace_enabled=False
            ),
            default_method_options={"authorizer": lambda_authorizer, "authorization_type": apigateway.AuthorizationType.CUSTOM}
        )

        codebuild_integration_role = iam.Role(self, "CodeBuildIntegrationRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com")
        )

        codebuild_integration_role.add_to_policy(iam.PolicyStatement(
            actions=["codebuild:StartBuild"],
            resources=[codebuild_project.project_arn]
        ))

        codebuild_integration = apigateway.AwsIntegration(
            service="codebuild",
            action="StartBuild",
            integration_http_method="POST",
            options=apigateway.IntegrationOptions(
                credentials_role=codebuild_integration_role,
                request_parameters={
                    "integration.request.header.Content-Type": "'application/x-amz-json-1.1'",
                    "integration.request.header.X-Amz-Target": "'CodeBuild_20161006.StartBuild'"
                },
                request_templates={
                    "application/json":
                        "#set($data = $util.escapeJavaScript($input.json('$')))"+
                        json.dumps({
                            "projectName": codebuild_project.project_name,
                            "environmentVariablesOverride": [
                                {
                                    "name": "JSON_PAYLOAD",
                                    "value": "$data",
                                    "type": "PLAINTEXT"
                                }
                            ]
                        })
                },
                integration_responses=[{
                    "statusCode": "200",
                    "responseTemplates": {
                        "application/json": "{\"message\": \"Build started\"}"
                    }
                }]
            )
        )

        api_resource = api.root.add_resource("build")
        api_resource.add_method("POST", codebuild_integration,
            method_responses=[{
                "statusCode": "200"
            }]
        )
        
        # Nag supresssion for Api gateway with custom Lambda authorizer enabled. 
        cdk_nag.NagSuppressions.add_resource_suppressions(api, [
        {
            "id": 'AwsSolutions-COG4',
            "reason": 'The API Gateway has custom lambda authorizer enabled.'
        },
        ],
        apply_to_children=True
        )

        # Nag supresssion for Cloudwatch Role using AWS Managed policy created as part of CDK. 
        cdk_nag.NagSuppressions.add_resource_suppressions(api, [
        {
            "id": 'AwsSolutions-IAM4',
            "reason": 'The Default Role provisioned as part of property cloud_watch_role set to true.'
        },
        ],
        apply_to_children=True
        )

        # Nag supresssion for API Validation. 
        cdk_nag.NagSuppressions.add_resource_suppressions(api, [
        {
            "id": 'AwsSolutions-APIG2',
            "reason": 'Not adding API validation as SNOW request for Account vending is different for every customer.'
        },
        ],
        apply_to_children=True
        )

        aws_cdk.CfnOutput(self, "SnowIntegrationAPIEndpoint", value=f"{api.url}build/")
        aws_cdk.CfnOutput(self, "SnowIntegrationPipelineURL", value=integration_pipeline_repo.repository_clone_url_grc)
        aws_cdk.CfnOutput(self, "SnowSecretsManagerArn", value=snow_secret.secret_full_arn)
        aws_cdk.CfnOutput(self, "ApiAuthParameterStoreArn", value=api_key_name.parameter_arn)
