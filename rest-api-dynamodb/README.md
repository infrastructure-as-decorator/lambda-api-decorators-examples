# REST API + DynamoDB

Independent AWS CDK Python example that builds a REST API backed by a real
DynamoDB table named `Orders`. It also creates an audit bucket whose read
permissions demonstrate role configuration. The five functions are grouped by
resource in `lambdas/orders.py`, while shared runtime code is provided by the
`orders` AWS Lambda Layer.

## Architecture

The stack contains one API Gateway REST API, one on-demand DynamoDB table with
string partition key `id`, one S3 audit bucket, and five independent Lambda
functions. Each function declares exactly one route:

| Method | Path | Access |
| --- | --- | --- |
| GET | `/orders` | DynamoDB read |
| GET | `/orders/{id}` | DynamoDB read |
| POST | `/orders` | DynamoDB write |
| PUT | `/orders/{id}` | DynamoDB write |
| DELETE | `/orders/{id}` | DynamoDB write |

The handlers import `orders_shared` from the `orders` Layer through the
standard Lambda `/opt/python` import root. `@layer("orders")` associates every
function with that Layer; the Layer does not grant DynamoDB permissions.

## Project layout

```text
rest-api-dynamodb/
├── lambdas/
│   ├── __init__.py
│   ├── orders.py
│   └── requirements.txt
└── layers/
    └── orders/
        ├── requirements.txt
        └── python/
            └── orders_shared.py
```

`lambdas/orders.py` contains `list_orders`, `get_order`, `create_order`,
`update_order`, and `delete_order`. The CDK application passes both
`lambda_path="lambdas"` and `layers_path="layers"` to `LambdaApi`, so the
published Layer directory is discovered and attached to each function.

The POST function demonstrates named configuration with Python 3.12, 1024 MB,
15 seconds, `STAGE` and `TABLE_NAME`, the mutable `api-role`, and the function
name `configured-handler`. Other functions use independent CDK-created roles
and the default Python 3.14 runtime. `api-role` receives read access to the
audit bucket through `grant_read`; the handlers do not use that bucket.

## Prerequisites

Install Python 3.14, Node.js 22, AWS CDK v2, Docker, and configure AWS
credentials. Docker is required because CDK packages each Python Lambda with
`PythonFunction`.

### Linux/macOS

```bash
cd rest-api-dynamodb
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### PowerShell

```powershell
Set-Location rest-api-dynamodb
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

### CMD

```cmd
cd rest-api-dynamodb
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
```

## Tests and synthesis

From this directory, run:

```bash
pytest -q
cdk synth --quiet
```

The repository-level pytest configuration enables `--import-mode=importlib` so
examples can keep their established test filenames.

## Bootstrap and deploy

Set the target account and region, then bootstrap and deploy:

```bash
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_REGION="us-east-1"
cdk bootstrap
cdk deploy
```

PowerShell:

```powershell
$env:CDK_DEFAULT_ACCOUNT = (aws sts get-caller-identity --query Account --output text)
$env:CDK_DEFAULT_REGION = "us-east-1"
cdk bootstrap
cdk deploy
```

The deployment output includes the API URL. Set it before trying the examples:

```bash
export API_URL="https://…execute-api…amazonaws.com/prod"
```

## Requests

```bash
curl "$API_URL/orders"
curl "$API_URL/orders/123"
curl -X POST "$API_URL/orders" -H 'content-type: application/json' \
  -d '{"id":"123","customer":"Ada","total":10}'
curl -X PUT "$API_URL/orders/123" -H 'content-type: application/json' \
  -d '{"customer":"Ada","total":12}'
curl -i -X DELETE "$API_URL/orders/123"
```

## Destroy

```bash
cdk destroy
```

Warning: `cdk destroy` deletes the DynamoDB table because its removal policy is
`RemovalPolicy.DESTROY`. All data in the table is permanently removed.
