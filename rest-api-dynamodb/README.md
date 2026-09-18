# REST API + DynamoDB CRUD

Este ejemplo despliega una API Gateway REST con cinco Lambdas y una tabla
DynamoDB real llamada `Orders`. La tabla tiene partition key string `id` y
`PAY_PER_REQUEST`. La aplicación no importa una tabla existente.

## Arquitectura y estructura

`LambdaApi` descubre los handlers decorados en `lambdas/`, crea la API REST,
las integraciones proxy y las Lambdas. `rest_api_dynamodb_stack.py` crea la
tabla, un role de Lambda con `AWSLambdaBasicExecutionRole`, registra los
recursos en `LambdaApiConfig` y publica el output `ApiUrl`.

```text
app.py
rest_api_dynamodb/rest_api_dynamodb_stack.py
lambdas/
  list_orders.py       GET /orders
  get_order.py         GET /orders/{order_id}
  create_order.py      POST /orders
  update_order.py      PUT /orders/{order_id}
  delete_order.py      DELETE /orders/{order_id}
  orders.py            utilidades DynamoDB y respuestas proxy
tests/
```

Todos los handlers devuelven respuestas Lambda proxy JSON, validan JSON y
campos requeridos, usan `TABLE_NAME` y responden `404` para órdenes ausentes.
Una orden requiere `id`, `customer`, `total` y `status` al crearla; PUT recibe
los tres últimos campos y conserva el id de la URL.

## Decoradores y configuración

El runtime predeterminado de `LambdaApiConfig` es Python 3.14. La tabla se
registra con la clave lógica `orders`, `STAGE=dev` y `TABLE_NAME=table.table_name`
se registran como entornos personalizados, y el role real se registra como
`api-role`. Sólo el endpoint POST usa ese role mediante `@role`.

El POST conserva exactamente esta configuración:

```python
@memory_size(1024)
@timeout(15)
@environment("STAGE", "TABLE_NAME")
@runtime("python3.12")
@role("api-role")
@description("Configured endpoint")
@name("configured-handler")
@POST("/orders")
@grant_dynamodb("orders", "write")
```

Los decoradores de configuración prevalecen sobre los defaults para ese
handler; por eso POST usa Python 3.12, 1024 MB, 15 segundos, la descripción y
el nombre indicados. Los otros cuatro handlers conservan Python 3.14.
`grant_dynamodb(..., "read")` genera permisos de lectura; `"write"` es
acumulativo y genera lectura y escritura. No hay permisos DynamoDB manuales ni
recursos globales `*`.

## Instalación y validación

Linux/macOS:

```bash
cd rest-api-dynamodb
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

PowerShell:

```powershell
cd rest-api-dynamodb
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

CMD:

```bat
cd rest-api-dynamodb
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-dev.txt
```

Se necesita Node.js 22, AWS CDK CLI y Docker para el bundling de Lambdas.
Instale el CLI con `npm install --global aws-cdk` y verifique `docker info`.
Las dependencias Python son distribuciones públicas de
`lambda-api-decorators` y `lambda-api-decorators-cdk`.

```bash
pytest -q
cdk synth --quiet
```

Para una cuenta nueva, haga bootstrap una vez:

```bash
cdk bootstrap aws://ACCOUNT_ID/REGION
```

## Deploy y endpoints

Configure credenciales y región AWS, y despliegue:

```bash
cdk deploy
```

Guarde la URL mostrada por el output `ApiUrl`:

```bash
API_URL="https://...execute-api..."
curl "$API_URL/orders"
curl "$API_URL/orders/order-1"
curl -X POST "$API_URL/orders" -H 'Content-Type: application/json' \
  -d '{"id":"order-1","customer":"Ada","total":42.50,"status":"new"}'
curl -X PUT "$API_URL/orders/order-1" -H 'Content-Type: application/json' \
  -d '{"customer":"Ada","total":45,"status":"paid"}'
curl -X DELETE "$API_URL/orders/order-1"
```

La tabla puede consultarse opcionalmente con:

```bash
aws dynamodb scan --table-name Orders
```

## Destrucción, datos y costos

`cdk destroy` elimina el stack completo: API Gateway, las cinco Lambdas, el
role/policies y la tabla `Orders`, incluidos todos sus datos. La tabla usa
explícitamente `RemovalPolicy.DESTROY`; no tiene protección contra eliminación
ni `RETAIN`. No ejecute ese comando si necesita conservar los datos. Mientras
el stack esté desplegado pueden generarse cargos de API Gateway, Lambda,
DynamoDB (incluyendo lecturas/escrituras), CloudWatch Logs y otros recursos
asociados a la cuenta.

El nombre físico `configured-handler` es intencional para demostrar
`@name`, pero puede colisionar si se despliegan varios stacks compatibles en
la misma región/cuenta. En ese caso elimine el stack anterior o use otra
cuenta/entorno; el ejemplo conserva el valor solicitado.
