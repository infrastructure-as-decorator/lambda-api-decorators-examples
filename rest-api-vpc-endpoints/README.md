# REST API with VPC Gateway Endpoints

This standalone AWS CDK example puts four independently deployed Lambda handlers in private isolated VPC subnets. The functions read and write DynamoDB and S3 through Gateway Endpoints, so the application does not need a NAT Gateway or public internet access.

## Architecture

The stack creates one VPC with isolated subnets in up to two Availability Zones, one DynamoDB table, one S3 bucket, one API Gateway REST API, and four Lambda functions. A DynamoDB Gateway Endpoint and an S3 Gateway Endpoint add routes to the route tables used by the isolated Lambda subnets. No NAT Gateway, NAT instance, interface endpoint, Secrets Manager call, STS call, or external HTTP call is part of this example.

Gateway Endpoints provide network reachability to these two AWS services. They do not authorize requests: the handler grants create least-privilege IAM policies for the registered table and bucket.

The endpoint types do not have an hourly endpoint charge, but DynamoDB, S3, Lambda, API Gateway, and other AWS usage can still incur charges. This is not a claim that the complete example is free.

## Project structure

```text
rest-api-vpc-endpoints/
├── app.py
├── cdk.json
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── lambdas/
│   ├── __init__.py
│   ├── items.py
│   ├── objects.py
│   └── requirements.txt
├── layers/
│   └── application/
│       ├── python/
│       │   ├── common.py
│       │   ├── repository.py
│       │   └── service.py
│       └── requirements.txt
├── rest_api_vpc_endpoints/
│   ├── __init__.py
│   └── rest_api_vpc_endpoints_stack.py
└── tests/
    ├── test_handlers.py
    └── test_stack.py
```

## Routes and entry points

| Method | Path | Lambda entry point | Service |
| --- | --- | --- | --- |
| POST | `/items` | `items.create_item` | DynamoDB write |
| GET | `/items/{id}` | `items.get_item` | DynamoDB read |
| POST | `/objects` | `objects.put_object` | S3 write |
| GET | `/objects/{key}` | `objects.get_object` | S3 read |

Each Python function declares exactly one route. The two modules are grouped only to keep the example small; CDK still creates one Lambda and one execution role per handler.

The `application` Lambda Layer contains the three application layers used by the handlers: `common.py` contains HTTP helpers, `service.py` contains validation and application behavior, and `repository.py` contains AWS SDK access. The handlers remain thin route adapters.

## Registries, grants, and IAM

The stack reads the CDK context value `stage`, defaulting to `develop`. The DynamoDB table is physically named `items-{stage}` (for example, `items-develop`). Lambdas receive only `STAGE` for this lookup; they do not receive a `TABLE_NAME` setting. The repository reads `STAGE` and derives the table name before creating the boto3 DynamoDB resource. The S3 bucket name remains supplied through its registered environment mapping.

The stack registers the actual CDK VPC, table, and bucket objects with `LambdaApiConfig`. It also registers environment mappings for the stage and bucket. The VPC is applied with `vpc` and `vpc_subnets=SubnetSelection(subnet_type=PRIVATE_ISOLATED)`, while the `vpc_registry` demonstrates the named resource registry supported by the released CDK package.

Registries are lookup mechanisms, not permissions. `@grant_dynamodb("items", "read")`, `@grant_dynamodb("items", "write")`, `@grant_s3("objects", "read")`, and `@grant_s3("objects", "write")` attach the required policies to the corresponding function. `write` is the library's native cumulative read/write grant. No shared execution role is configured, so the CDK integration creates isolated roles and prevents permissions from accumulating across handlers.

The Lambda packaging boundary declares `lambda-api-decorators==0.3.4`. The AWS Lambda Python runtime supplies boto3; `requirements-dev.txt` additionally installs boto3 so mocked handler tests can run locally. No local, editable, Git, or sibling-library dependency is used.

## Requirements and installation

Use Python 3.14, Node.js 22, Docker, and an AWS account configured for CDK. Install the pinned published packages and development dependencies from PyPI.

Linux/macOS:

```bash
cd rest-api-vpc-endpoints
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm install --global aws-cdk
```

PowerShell:

```powershell
Set-Location rest-api-vpc-endpoints
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm install --global aws-cdk
```

Command Prompt:

```cmd
cd rest-api-vpc-endpoints
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
npm install --global aws-cdk
```

## Test and synthesize

Docker is required because `PythonFunction` bundles each Lambda. Run:

```bash
pytest -q
python -m compileall -q lambdas layers tests
cdk synth --quiet
```

The synthesized template should contain one application VPC, zero NAT Gateways, two Gateway VPC Endpoints, four application Lambdas, four application roles, the REST API, the table, and the bucket. S3 automatic cleanup may add a CDK-managed cleanup custom resource; that resource is not an application Lambda and is not placed in the VPC.

## Deploy

Bootstrap the target account and Region once if needed:

```bash
cdk bootstrap
```

Deploy the default `develop` stage:

```bash
cdk deploy -c stage=develop
```

To deploy a separate environment, use another stage value such as `qa` or `prod`. The table name changes accordingly:

```bash
cdk deploy -c stage=qa
```

Copy the `ApiUrl` output. The following examples use `API_URL` as a shell variable and store plain text objects. The `{key}` route is intended for a simple key such as `greeting.txt`.

```bash
API_URL="https://...execute-api..."

curl -i -X POST "$API_URL/items" \
  -H 'Content-Type: application/json' \
  -d '{"id":"1","value":"Ada"}'

curl -i "$API_URL/items/1"

curl -i -X POST "$API_URL/objects" \
  -H 'Content-Type: application/json' \
  -d '{"key":"greeting.txt","body":"hello from a private Lambda"}'

curl -i "$API_URL/objects/greeting.txt"
```

Expected successful responses are JSON: the item create returns `201` with the stored object, item read returns `200` with that object, object write returns `201` with `{"key":"greeting.txt"}`, and object read returns `200` with `{"key":"greeting.txt","body":"hello from a private Lambda"}`. Invalid input returns `400`; missing resources return `404`; handled AWS failures return `502` without internal exception details.

For PowerShell, the equivalent requests are:

```powershell
$ApiUrl = "https://...execute-api..."
Invoke-RestMethod -Method Post -Uri "$ApiUrl/items" -ContentType "application/json" -Body '{"id":"1","value":"Ada"}'
Invoke-RestMethod -Method Get -Uri "$ApiUrl/items/1"
Invoke-RestMethod -Method Post -Uri "$ApiUrl/objects" -ContentType "application/json" -Body '{"key":"greeting.txt","body":"hello from a private Lambda"}'
Invoke-RestMethod -Method Get -Uri "$ApiUrl/objects/greeting.txt"
```

For CMD, use the same `curl` commands after setting the URL:

```cmd
set API_URL=https://...execute-api...
curl -i -X POST "%API_URL%/items" -H "Content-Type: application/json" -d "{\"id\":\"1\",\"value\":\"Ada\"}"
curl -i "%API_URL%/items/1"
curl -i -X POST "%API_URL%/objects" -H "Content-Type: application/json" -d "{\"key\":\"greeting.txt\",\"body\":\"hello from a private Lambda\"}"
curl -i "%API_URL%/objects/greeting.txt"
```

## Cleanup

```bash
cdk destroy
```

This stack is intentionally disposable. `cdk destroy -c stage=develop` permanently deletes the stage-specific DynamoDB table, the S3 bucket, and all objects in that bucket because both resources use `RemovalPolicy.DESTROY` and the bucket enables `auto_delete_objects`. Back up anything important before running the command.
