from lambda_api_decorators import (
    DELETE,
    GET,
    POST,
    PUT,
    description,
    environment,
    grant_dynamodb,
    layer,
    memory_size,
    name,
    role,
    runtime,
    timeout,
)

from orders_shared import order_id, request_json, response, table


@GET("/orders")
@layer("orders")
@grant_dynamodb("orders", "read")
@environment("TABLE_NAME")
def list_orders(event, context):
    items = table().scan().get("Items", [])
    return response(200, items)


@GET("/orders/{id}")
@layer("orders")
@grant_dynamodb("orders", "read")
@environment("TABLE_NAME")
def get_order(event, context):
    item = table().get_item(Key={"id": order_id(event)}).get("Item")
    if item is None:
        return response(404, {"error": "Order not found"})
    return response(200, item)


@POST("/orders")
@layer("orders")
@grant_dynamodb("orders", "write")
@memory_size(1024)
@timeout(15)
@environment("STAGE", "TABLE_NAME")
@runtime("python3.12")
@role("api-role")
@description("Configured endpoint")
@name("configured-handler")
def create_order(event, context):
    order, error = request_json(event)
    if error:
        return error
    if "id" not in order:
        return response(400, {"error": "Missing required fields", "fields": ["id"]})
    table().put_item(Item=order, ConditionExpression="attribute_not_exists(id)")
    return response(201, order)


@PUT("/orders/{id}")
@layer("orders")
@grant_dynamodb("orders", "write")
@environment("TABLE_NAME")
def update_order(event, context):
    identifier = order_id(event)
    order, error = request_json(event)
    if error:
        return error
    existing = table().get_item(Key={"id": identifier}).get("Item")
    if existing is None:
        return response(404, {"error": "Order not found"})
    updated = {"id": identifier, **order}
    table().put_item(Item=updated)
    return response(200, updated)


@DELETE("/orders/{id}")
@layer("orders")
@grant_dynamodb("orders", "write")
@environment("TABLE_NAME")
def delete_order(event, context):
    deleted = table().delete_item(
        Key={"id": order_id(event)}, ReturnValues="ALL_OLD"
    ).get("Attributes")
    if deleted is None:
        return response(404, {"error": "Order not found"})
    return response(204, None)
