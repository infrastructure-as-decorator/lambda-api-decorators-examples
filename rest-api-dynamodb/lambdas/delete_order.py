from lambda_api_decorators import DELETE, environment, grant_dynamodb

from orders import order_id, response, table


@DELETE("/orders/{id}")
@grant_dynamodb("orders", "write")
@environment("TABLE_NAME")
def lambda_handler(event, context):
    deleted = table().delete_item(
        Key={"id": order_id(event)}, ReturnValues="ALL_OLD"
    ).get("Attributes")
    if deleted is None:
        return response(404, {"error": "Order not found"})
    return response(204, None)
