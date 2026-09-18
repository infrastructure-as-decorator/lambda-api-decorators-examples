from lambda_api_decorators import DELETE, grant_dynamodb

from orders import order_id, response, table


@DELETE("/orders/{order_id}")
@grant_dynamodb("orders", "write")
def lambda_handler(event, context):
    deleted = table().delete_item(
        Key={"id": order_id(event)}, ReturnValues="ALL_OLD"
    ).get("Attributes")
    if deleted is None:
        return response(404, {"error": "Order not found"})
    return response(200, deleted)
