from aws_cdk import CfnOutput, Stack, aws_lambda as lambda_
from constructs import Construct
from lambda_api_decorators_cdk import ApiType, LambdaApi, LambdaApiConfig


class HttpApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config = LambdaApiConfig(
            runtime=lambda_.Runtime.PYTHON_3_14,
        )

        api = LambdaApi(
            self,
            "Api",
            lambda_path="lambdas",
            api_type=ApiType.HTTP,
            config=config,
        )

        CfnOutput(self, "HttpApiEndpoint", value=api.api.api_endpoint)
