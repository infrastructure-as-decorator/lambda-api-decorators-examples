from lambda_api_decorators import GET, POST, environment, grant_dynamodb, layer

from common import path_parameter, request_json, response
from service import (
    InvalidRequestError,
    NotFoundError,
    StorageError,
    create_item as create_item_service,
    get_item as get_item_service,
)


@POST("/items")
@layer("application")
@environment("stage")
@grant_dynamodb("items", "write")
def create_item(event, context):
    item, error = request_json(event)
    if error:
        return error
    try:
        return response(201, create_item_service(item))
    except InvalidRequestError as error:
        return response(400, {"error": str(error), "fields": ["id"]})
    except StorageError:
        return response(502, {"error": "DynamoDB request failed"})


@GET("/items/{id}")
@layer("application")
@environment("stage")
@grant_dynamodb("items", "read")
def get_item(event, context):
    identifier = path_parameter(event, "id")
    if not identifier:
        return response(400, {"error": "Missing required path parameter"})
    try:
        return response(200, get_item_service(identifier))
    except NotFoundError:
        return response(404, {"error": "Item not found"})
    except StorageError:
        return response(502, {"error": "DynamoDB request failed"})
