from lambda_api_decorators import (
    POST,
    description,
    environment,
    grant_dynamodb,
    memory_size,
    name,
    role,
    runtime,
    timeout,
)

from orders import request_json, response, table


@POST("/orders")
@grant_dynamodb("orders", "write")
@memory_size(1024)
@timeout(15)
@environment("STAGE", "TABLE_NAME")
@runtime("python3.12")
@role("api-role")
@description("Configured endpoint")
@name("configured-handler")
def lambda_handler(event, context):
    order, error = request_json(event)
    if error:
        return error
    if "id" not in order:
        return response(400, {"error": "Missing required fields", "fields": ["id"]})
    table().put_item(Item=order, ConditionExpression="attribute_not_exists(id)")
    return response(201, order)
