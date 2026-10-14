#!/usr/bin/env python3
import aws_cdk as cdk

from rest_api_vpc_endpoints.rest_api_vpc_endpoints_stack import RestApiVpcEndpointsStack


app = cdk.App()
RestApiVpcEndpointsStack(app, "RestApiVpcEndpointsStack")
app.synth()
