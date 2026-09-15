from aws_cdk import Stack
from constructs import Construct
from lambda_api_decorators_cdk import LambdaApi


class QuickstartRestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        LambdaApi(
            self,
            "Api",
            source="lambdas",
            runtime="python3.14",
        )
