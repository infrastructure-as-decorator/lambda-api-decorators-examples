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

Install the CDK app dependencies:

```console
python -m pip install -r requirements.txt
```

Synthesize the CloudFormation template (Docker must be running):

```console
cdk synth
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
