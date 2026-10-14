from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class RestApiDynamodbStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stage = self.node.try_get_context("stage") or "dev"
        table_name = f"{stage}-orders"

        table = dynamodb.Table(
            self,
            "Orders",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        audit_bucket = s3.Bucket(
            self,
            "OrdersAudit",
            removal_policy=RemovalPolicy.DESTROY,
        )

        api_role = iam.Role(
            self,
            "ApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        audit_bucket.grant_read(api_role)

        config = LambdaApiConfig(
            default_runtime="python3.14",
            common_environment={"SERVICE": "orders"},
            environment_registry={
                "STAGE": {"STAGE": stage},
            },
            role_registry={"api-role": api_role},
            dynamodb_table_registry={"orders": table},
        )

        api = LambdaApi(
            self,
            "Api",
            lambda_path="lambdas",
            layers_path="layers",
            config=config,
            endpoint_type=apigateway.EndpointType.REGIONAL,
        )
        CfnOutput(self, "ApiUrl", value=api.api.url)
