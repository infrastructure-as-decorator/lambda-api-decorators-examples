#!/usr/bin/env python3
import aws_cdk as cdk

from rest_api_dynamodb.rest_api_dynamodb_stack import RestApiDynamodbStack


app = cdk.App()
RestApiDynamodbStack(app, "RestApiDynamodbStack")
app.synth()
