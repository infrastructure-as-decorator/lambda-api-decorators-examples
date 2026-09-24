from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from constructs import Construct
from lambda_api_decorators_cdk import LambdaApi, LambdaApiConfig


class RestApiCognitoAuthorizerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            sign_in_aliases=cognito.SignInAliases(username=True),
            self_sign_up_enabled=False,
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        user_pool_client = user_pool.add_client(
            "UserPoolClient",
            auth_flows=cognito.AuthFlow(user_password=True),
            generate_secret=False,
        )
        rest_api = apigateway.RestApi(self, "RestApi")
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )

        config = LambdaApiConfig(
            default_runtime="python3.14",
            authorizer_registry={
                "cognito": cognito_authorizer,
            },
            default_authorizer="cognito",
        )
        api = LambdaApi(
            self,
            "Api",
            lambda_path="lambdas",
            api=rest_api,
            config=config,
        )

        CfnOutput(self, "ApiUrl", value=api.api.url)
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=user_pool_client.user_pool_client_id)
