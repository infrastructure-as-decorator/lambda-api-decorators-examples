from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_s3 as s3
from constructs import Construct
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class RestApiVpcEndpointsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                )
            ],
        )
        isolated_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
        )
        vpc.add_gateway_endpoint(
            "DynamoDbGatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[isolated_subnets],
        )
        vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[isolated_subnets],
        )

        stage = self.node.try_get_context("stage") or "develop"
        table_name = f"items-{stage}"

        table = dynamodb.Table(
            self,
            "Items",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        bucket = s3.Bucket(
            self,
            "Objects",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        config = LambdaApiConfig(
            default_runtime="python3.14",
            vpc=vpc,
            vpc_subnets=isolated_subnets,
            vpc_registry={"private": vpc},
            environment_registry={
                "stage": {"STAGE": stage},
                "objects": {"BUCKET_NAME": bucket.bucket_name},
            },
            dynamodb_table_registry={"items": table},
            s3_bucket_registry={"objects": bucket},
        )
        api = LambdaApi(
            self,
            "Api",
            lambda_path="lambdas",
            layers_path="layers",
            config=config,
        )

        CfnOutput(self, "ApiUrl", value=api.api.url)
