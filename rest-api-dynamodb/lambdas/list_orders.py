import json

from lambda_api_decorators import GET, grant_dynamodb

from orders import response, table


@GET("/orders")
@grant_dynamodb("orders", "read")
def lambda_handler(event, context):
    items = table().scan().get("Items", [])
    return response(200, items)
