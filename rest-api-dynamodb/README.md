# REST API + DynamoDB

Independent AWS CDK Python example that builds a REST API backed by a real
DynamoDB table named `<stage>-orders` (for example, `dev-orders`). It also
creates an audit bucket whose read permissions demonstrate role configuration.
The five functions are grouped by resource in `lambdas/orders.py`, while
persistence functions and shared runtime code are provided by the `orders` AWS
Lambda Layer.

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
Handlers parse requests, validate input, and create HTTP responses. The Layer
owns table access through `list_order_records`, `find_order`,
`create_order_record`, `update_order_record`, and `delete_order_record`.

This example explicitly selects a Regional REST API with
`apigateway.EndpointType.REGIONAL`. Regional APIs do not use API Gateway's
managed Edge-Optimized CloudFront distribution. To select EDGE instead, omit
`endpoint_type` or specify `apigateway.EndpointType.EDGE`.

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
        └── orders_shared.py
```

`lambdas/orders.py` contains `list_orders`, `get_order`, `create_order`,
`update_order`, and `delete_order`. The CDK application passes both
`lambda_path="lambdas"` and `layers_path="layers"` to `LambdaApi`, so the
published Layer directory is discovered and attached to each function.

The physical table name is deterministic and derived from `STAGE` as
`<stage>-orders`. The default stage is `dev`, so the default table is
`dev-orders`. The Layer derives the name from `STAGE` when it obtains the
DynamoDB resource, and the CDK stack uses the same stage and convention for
the physical table. Lambda functions receive `STAGE`; they do not receive a
`TABLE_NAME` environment setting. The existing
`@grant_dynamodb("orders", "read")` and
`@grant_dynamodb("orders", "write")` declarations provide IAM access.

Each handler has one HTTP route, and the route decorator is immediately above
the handler definition. Other decorators configure the Layer, grants, and
Lambda settings above that route decorator.

The POST function demonstrates named configuration with Python 3.12, 1024 MB,
15 seconds, `STAGE`, the mutable `api-role`, and the function name
`configured-handler`. Other functions use independent CDK-created roles and
the default Python 3.14 runtime. `api-role` receives read access to the
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

`POST /orders` returns `201 Created` when the order is created and `409
Conflict` when an order with the same `id` already exists. The Layer uses
DynamoDB's atomic conditional write (`attribute_not_exists(id)`) so an
existing order cannot be overwritten.

To reproduce the duplicate-order response, send the same order twice:

```bash
ORDER='{"id":"duplicate-example","customer":"Ada","total":10,"status":"new"}'
curl -i -X POST "$API_URL/orders" -H 'content-type: application/json' -d "$ORDER"
# HTTP/1.1 201 Created
curl -i -X POST "$API_URL/orders" -H 'content-type: application/json' -d "$ORDER"
# HTTP/1.1 409 Conflict
# {"error": "Order already exists"}
```

## Destroy

```bash
cdk destroy
```

Warning: `cdk destroy` deletes the DynamoDB table because its removal policy is
`RemovalPolicy.DESTROY`. All data in the table is permanently removed.
