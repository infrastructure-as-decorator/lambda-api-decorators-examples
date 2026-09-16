# HTTP API

This independent AWS CDK app demonstrates `LambdaApi` with API Gateway HTTP
API. It creates one Lambda function and one `GET /hello` route, returning a
JSON response.

## Prerequisites

- Python 3.10 or newer
- Node.js 22 or newer
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- Docker (used by CDK to bundle the Lambda source)
- AWS credentials, only for `cdk bootstrap`, `cdk deploy`, and `cdk destroy`

Creating the environment, installing dependencies, and running `cdk synth` do
not require AWS credentials.

## Set up

Run these commands from this directory:

```console
python -m venv .venv
python -m pip install -r requirements-dev.txt
pytest -q
cdk synth --quiet
```

Activate the environment on Linux or macOS with:

```console
source .venv/bin/activate
```

With PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

With Command Prompt (CMD):

```bat
.venv\Scripts\activate.bat
```

The infrastructure test and CDK synthesis require Docker to be installed and
running.

## Deploy

Configure AWS credentials, then bootstrap the account and Region once:

```console
cdk bootstrap
cdk deploy
```

Copy the `HttpApiEndpoint` output and call the route:

```console
curl "https://YOUR_HTTP_API_ID.execute-api.YOUR_REGION.amazonaws.com/hello"
```

The response is:

```json
{"message": "Hello from HTTP API!"}
```

## Clean up

```console
cdk destroy
```
