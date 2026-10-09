import os

import boto3
from lambda_api_decorators import GET, POST, environment, grant_dynamodb

from common import path_parameter, request_json, response


def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


@POST("/items")
@environment("items")
@grant_dynamodb("items", "write")
def create_item(event, context):
    item, error = request_json(event)
    if error:
        return error
    if not item.get("id"):
        return response(400, {"error": "Missing required fields", "fields": ["id"]})
    try:
        table().put_item(Item=item)
    except Exception:
        return response(502, {"error": "DynamoDB request failed"})
    return response(201, item)


@GET("/items/{id}")
@environment("items")
@grant_dynamodb("items", "read")
def get_item(event, context):
    identifier = path_parameter(event, "id")
    if not identifier:
        return response(400, {"error": "Missing required path parameter"})
    try:
        result = table().get_item(Key={"id": identifier})
    except Exception:
        return response(502, {"error": "DynamoDB request failed"})
    item = result.get("Item")
    if item is None:
        return response(404, {"error": "Item not found"})
    return response(200, item)
