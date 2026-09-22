from lambda_api_decorators import PUT, environment, grant_dynamodb

from orders import order_id, request_json, response, table


@PUT("/orders/{id}")
@grant_dynamodb("orders", "write")
@environment("TABLE_NAME")
def lambda_handler(event, context):
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
