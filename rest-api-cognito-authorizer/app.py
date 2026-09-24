#!/usr/bin/env python3
import aws_cdk as cdk

from rest_api_cognito_authorizer.rest_api_cognito_authorizer_stack import (
    RestApiCognitoAuthorizerStack,
)


app = cdk.App()
RestApiCognitoAuthorizerStack(app, "RestApiCognitoAuthorizerStack")
app.synth()
