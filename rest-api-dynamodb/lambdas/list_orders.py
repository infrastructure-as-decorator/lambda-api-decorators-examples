from lambda_api_decorators import GET, environment, grant_dynamodb

from orders import response, table


@GET("/orders")
@grant_dynamodb("orders", "read")
@environment("TABLE_NAME")
def lambda_handler(event, context):
    items = table().scan().get("Items", [])
    return response(200, items)
