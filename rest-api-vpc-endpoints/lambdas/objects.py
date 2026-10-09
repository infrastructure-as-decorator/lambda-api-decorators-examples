from lambda_api_decorators import GET, POST, environment, grant_s3, layer

from common import path_parameter, request_json, response
from service import (
    InvalidRequestError,
    NotFoundError,
    StorageError,
    get_object as get_object_service,
    put_object as put_object_service,
)


@POST("/objects")
@layer("application")
@environment("stage", "objects")
@grant_s3("objects", "write")
def put_object(event, context):
    payload, error = request_json(event)
    if error:
        return error
    try:
        key = put_object_service(payload)
    except InvalidRequestError:
        return response(400, {"error": "Object key and body are required"})
    except StorageError:
        return response(502, {"error": "S3 request failed"})
    return response(201, {"key": key})


@GET("/objects/{key}")
@layer("application")
@environment("stage", "objects")
@grant_s3("objects", "read")
def get_object(event, context):
    key = path_parameter(event, "key")
    if not key:
        return response(400, {"error": "Missing required path parameter"})
    try:
        stored = get_object_service(key)
    except NotFoundError:
        return response(404, {"error": "Object not found"})
    except StorageError:
        return response(502, {"error": "S3 request failed"})
    return response(200, {"key": key, "body": stored})
