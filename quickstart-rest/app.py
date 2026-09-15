#!/usr/bin/env python3
import aws_cdk as cdk

from quickstart_rest.quickstart_rest_stack import QuickstartRestStack


app = cdk.App()
QuickstartRestStack(app, "QuickstartRestStack")

app.synth()
