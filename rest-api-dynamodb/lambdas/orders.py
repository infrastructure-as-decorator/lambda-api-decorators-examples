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

from orders_shared import (
    create_order_record,
    delete_order_record,
    find_order,
    list_order_records,
    order_id,
    request_json,
    response,
    update_order_record,
)


@layer("orders")
@grant_dynamodb("orders", "read")
@environment("STAGE")
@GET("/orders")
def list_orders(event, context):
    return response(200, list_order_records())


@layer("orders")
@grant_dynamodb("orders", "read")
@environment("STAGE")
@GET("/orders/{id}")
def get_order(event, context):
    item = find_order(order_id(event))
    if item is None:
        return response(404, {"error": "Order not found"})
    return response(200, item)


@layer("orders")
@grant_dynamodb("orders", "write")
@memory_size(1024)
@timeout(15)
@environment("STAGE")
@runtime("python3.12")
@role("api-role")
@description("Configured endpoint")
@name("configured-handler")
@POST("/orders")
def create_order(event, context):
    order, error = request_json(event)
    if error:
        return error
    if "id" not in order:
        return response(400, {"error": "Missing required fields", "fields": ["id"]})
    create_order_record(order)
    return response(201, order)


@layer("orders")
@grant_dynamodb("orders", "write")
@environment("STAGE")
@PUT("/orders/{id}")
def update_order(event, context):
    identifier = order_id(event)
    order, error = request_json(event)
    if error:
        return error
    existing = find_order(identifier)
    if existing is None:
        return response(404, {"error": "Order not found"})
    updated = update_order_record(identifier, order)
    return response(200, updated)


@layer("orders")
@grant_dynamodb("orders", "write")
@environment("STAGE")
@DELETE("/orders/{id}")
def delete_order(event, context):
    deleted = delete_order_record(order_id(event))
    if deleted is None:
        return response(404, {"error": "Order not found"})
    return response(204, None)
