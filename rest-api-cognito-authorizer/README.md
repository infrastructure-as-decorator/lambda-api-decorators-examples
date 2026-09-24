# REST API with a Cognito authorizer

This independent AWS CDK application demonstrates a REST API with Cognito as
the default authorizer. `/health` is public by explicit `@public` override;
`/me` inherits Cognito from `LambdaApiConfig`. Both handlers share
`lambdas/auth.py`, while the CDK integration creates two independent Lambda
functions.

## Architecture

```text
Client
  ├─ GET /health → explicit @public override → health Lambda
  └─ GET /me     → Cognito authorizer       → me Lambda
```

## Project structure

```text
rest-api-cognito-authorizer/
├── app.py
├── cdk.json
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── lambdas/
│   ├── __init__.py
│   ├── auth.py
│   └── requirements.txt
├── rest_api_cognito_authorizer/
│   ├── __init__.py
│   └── rest_api_cognito_authorizer_stack.py
└── tests/
    ├── test_handlers.py
    └── test_stack.py
```

## Routes

| Function | Entrypoint | Method | Path | Effective authorization |
| --- | --- | --- | --- | --- |
| `health` | `auth.health` | GET | `/health` | Public through `@public` |
| `me` | `auth.me` | GET | `/me` | Cognito inherited from `default_authorizer` |

## Stack

The stack creates one User Pool, one secret-free client, one Cognito REST
authorizer, one REST API, and two Lambda functions:

The CDK integration dependency is pinned to `lambda-api-decorators-cdk==0.4.5`.

```python
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
```

`self_sign_up_enabled=False` leaves user creation administrative. No user,
password, token, or client secret is placed in CloudFormation. The pool uses
`RemovalPolicy.DESTROY`, and the client enables `USER_PASSWORD_AUTH` with
`GenerateSecret: false`.

## Handlers

The complete `lambdas/auth.py` is:

```python
import json

from lambda_api_decorators import GET, public


JSON_HEADERS = {"Content-Type": "application/json"}


@GET("/health")
@public
def health(event, context):
    return {
        "statusCode": 200,
        "headers": JSON_HEADERS,
        "body": json.dumps({"status": "ok"}),
    }


@GET("/me")
def me(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims")
    )
    if not isinstance(claims, dict) or not claims.get("sub"):
        return {
            "statusCode": 401,
            "headers": JSON_HEADERS,
            "body": json.dumps({"message": "Unauthorized"}),
        }

    body = {"sub": claims["sub"]}
    if claims.get("cognito:username"):
        body["username"] = claims["cognito:username"]
    return {
        "statusCode": 200,
        "headers": JSON_HEADERS,
        "body": json.dumps(body),
    }
```

## Security model

`authorizer_registry` maps the logical key `cognito` to the real CDK
`CognitoUserPoolsAuthorizer`. `default_authorizer="cognito"` makes an
undecorated route inherit that authorizer, so `/me` does not repeat
`@authorizer("cognito")`. `@public` is an explicit per-route override that
makes only `/health` use `AuthorizationType: NONE`.

API Gateway validates `/me` before invoking the Lambda. The handler reads REST
API claims from `event["requestContext"]["authorizer"]["claims"]` and returns
only `sub` and the optional `cognito:username`. Its defensive `401` is for
direct invocation or malformed events. No handler calls AWS services.

## Tests

The handler tests cover proxy shape, status codes, JSON bodies, REST claims,
missing claims, sensitive-data exclusion, exact decorators, one route per
function, and absence of AWS calls. The stack tests cover Cognito resources,
deletion policies, secret-free client configuration, REST authorization for
both paths, two Python 3.14 entrypoints, outputs, registry inheritance, and
consolidated diagnostics.

## Prerequisites

- Python 3.14
- Node.js 22
- AWS CDK CLI
- Docker running and reachable by the current user
- AWS CLI, credentials, and a configured Region

Docker is required for CDK's Lambda bundling. AWS credentials are required for
bootstrap, deploy, Cognito CLI commands, and destroy, but not for tests or
synthesis.

## Installation

### Linux/macOS

```bash
cd rest-api-cognito-authorizer
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### PowerShell

```powershell
Set-Location rest-api-cognito-authorizer
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

### CMD

```bat
cd rest-api-cognito-authorizer
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
```

## Validate, bootstrap, and deploy

From `rest-api-cognito-authorizer`:

```text
pytest
cdk synth
cdk bootstrap
cdk deploy
```

The stack name is `RestApiCognitoAuthorizerStack`. Its outputs are
`ApiUrl`, `UserPoolId`, and `UserPoolClientId`.

## Create a user

The client uses `USER_PASSWORD_AUTH`. The following commands create an
administrative user without sending an invitation, then make its password
permanent. Do not commit passwords or tokens.

### Linux/macOS

```bash
STACK_NAME=RestApiCognitoAuthorizerStack
USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text)
CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' --output text)
API_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)
read -r USERNAME
read -r -s PASSWORD
printf '\n'
aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --username "$USERNAME" --temporary-password "$PASSWORD" --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --username "$USERNAME" --password "$PASSWORD" --permanent
export USER_POOL_ID CLIENT_ID API_URL USERNAME PASSWORD
```

Read the username and password interactively; do not paste the password into a
tracked file or script.

### PowerShell

```powershell
$StackName = "RestApiCognitoAuthorizerStack"
$UserPoolId = aws cloudformation describe-stacks --stack-name $StackName --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text
$ClientId = aws cloudformation describe-stacks --stack-name $StackName --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' --output text
$ApiUrl = aws cloudformation describe-stacks --stack-name $StackName --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text
$Username = Read-Host "Cognito username"
$SecurePassword = Read-Host "Cognito password" -AsSecureString
$Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr) }
aws cognito-idp admin-create-user --user-pool-id $UserPoolId --username $Username --temporary-password $Password --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $UserPoolId --username $Username --password $Password --permanent
```

The plain password string exists only temporarily for the AWS CLI process.

### CMD

```bat
set STACK_NAME=RestApiCognitoAuthorizerStack
for /f "delims=" %i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --query "Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue" --output text') do set USER_POOL_ID=%i
for /f "delims=" %i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --query "Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue" --output text') do set CLIENT_ID=%i
for /f "delims=" %i in ('aws cloudformation describe-stacks --stack-name %STACK_NAME% --query "Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue" --output text') do set API_URL=%i
set /p USERNAME=Cognito username:
set /p PASSWORD=Cognito password:
aws cognito-idp admin-create-user --user-pool-id %USER_POOL_ID% --username %USERNAME% --temporary-password %PASSWORD% --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id %USER_POOL_ID% --username %USERNAME% --password %PASSWORD% --permanent
```

`set /p` may echo the password in CMD. Use a terminal with hidden input for
real credentials and clear the variables afterward.

## Obtain an ID token

Cognito returns an ID token, access token, and refresh token. This example uses
the ID token in `Authorization`, because it carries the identity claims read by
the REST Cognito authorizer. Keep it in a temporary variable only.

### Linux/macOS

```bash
export ID_TOKEN=$(aws cognito-idp initiate-auth --client-id "$CLIENT_ID" --auth-flow USER_PASSWORD_AUTH --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" --query 'AuthenticationResult.IdToken' --output text)
```

### PowerShell

```powershell
$Auth = aws cognito-idp initiate-auth --client-id $ClientId --auth-flow USER_PASSWORD_AUTH --auth-parameters USERNAME=$Username,PASSWORD=$Password | ConvertFrom-Json
$IdToken = $Auth.AuthenticationResult.IdToken
```

### CMD

```bat
for /f "delims=" %i in ('aws cognito-idp initiate-auth --client-id %CLIENT_ID% --auth-flow USER_PASSWORD_AUTH --auth-parameters USERNAME=%USERNAME%,PASSWORD=%PASSWORD% --query "AuthenticationResult.IdToken" --output text') do set ID_TOKEN=%i
```

## Invoke the endpoints

`/health` without a token returns `200`. `/me` without a token is rejected by
API Gateway; with the ID token it returns the user's identifiers.

### Linux/macOS

```bash
curl --fail "$API_URL/health"
curl -i "$API_URL/me"
curl --fail -H "Authorization: $ID_TOKEN" "$API_URL/me"
```

### PowerShell

```powershell
Invoke-RestMethod "$ApiUrl/health"
Invoke-WebRequest "$ApiUrl/me" -SkipHttpErrorCheck
Invoke-RestMethod "$ApiUrl/me" -Headers @{ Authorization = $IdToken }
```

### CMD

```bat
curl --fail "%API_URL%/health"
curl -i "%API_URL%/me"
curl --fail -H "Authorization: %ID_TOKEN%" "%API_URL%/me"
```

The successful protected body is:

```json
{"sub": "user-id", "username": "alice"}
```

## Cleanup

```text
cdk destroy
```

Destroying the stack permanently deletes the Cognito User Pool and all users
stored in it.
