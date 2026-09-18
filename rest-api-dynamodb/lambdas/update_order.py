from lambda_api_decorators import PUT, grant_dynamodb

from orders import missing_fields, order_id, request_json, response, table


@PUT("/orders/{order_id}")
@grant_dynamodb("orders", "write")
def lambda_handler(event, context):
    identifier = order_id(event)
    order, error = request_json(event)
    if error:
        return error
    missing = missing_fields(order)
    if missing:
        return response(400, {"error": "Missing required fields", "fields": missing})
    existing = table().get_item(Key={"id": identifier}).get("Item")
    if existing is None:
        return response(404, {"error": "Order not found"})
    updated = {"id": identifier, **order}
    table().put_item(Item=updated)
    return response(200, updated)
