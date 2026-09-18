from lambda_api_decorators import GET, grant_dynamodb

from orders import order_id, response, table


@GET("/orders/{order_id}")
@grant_dynamodb("orders", "read")
def lambda_handler(event, context):
    item = table().get_item(Key={"id": order_id(event)}).get("Item")
    if item is None:
        return response(404, {"error": "Order not found"})
    return response(200, item)
