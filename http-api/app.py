#!/usr/bin/env python3
import aws_cdk as cdk

from http_api.http_api_stack import HttpApiStack


app = cdk.App()
HttpApiStack(app, "HttpApiStack")

app.synth()
