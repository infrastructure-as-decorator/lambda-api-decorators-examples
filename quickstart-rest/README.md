# Quick Start REST API

This independent AWS CDK app defines a default REST API backed by a single
Lambda handler for `GET /hello`.

## Prerequisites

- Python 3.10 or newer
- Node.js
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- Docker (used by CDK to bundle the Lambda source)
- AWS credentials, only for `cdk bootstrap`, `cdk deploy`, and `cdk destroy`

Creating the environment, installing dependencies, and running `cdk synth` do
not require AWS credentials.

## Stack

The stack configures the Lambda source directory and Python runtime explicitly:

```python
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
```

## Set up

From this directory, create a virtual environment:

```console
python -m venv .venv
```

Activate it on Linux or macOS:

```console
source .venv/bin/activate
```

Or activate it with PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or activate it with Command Prompt (CMD):

```bat
.venv\Scripts\activate.bat
```

Install the CDK app and test dependencies, then run the complete test suite:

```console
python -m pip install -r requirements-dev.txt
pytest -q
```

The infrastructure tests and CDK synthesis bundle the Lambda source, so Docker
must be installed and running for both. Synthesize the CloudFormation template
with:

```console
cdk synth --quiet
```

## Deploy (optional)

These commands use your configured AWS credentials. Bootstrap each AWS
account and Region once, then deploy the stack:

```console
cdk bootstrap
cdk deploy
```

The deployment outputs the REST API endpoint. Append `/hello` to call the
example route.

## Clean up

Deleting the deployed stack also requires AWS credentials:

```console
cdk destroy
```
