from aws_cdk import Stack, aws_lambda as lambda_
from constructs import Construct
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class QuickstartRestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config = LambdaApiConfig(
            runtime=lambda_.Runtime.PYTHON_3_14,
        )

        LambdaApi(
            self,
            "Api",
            lambda_path="lambdas",
            config=config,
        )
