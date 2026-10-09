import os

import boto3
from lambda_api_decorators import GET, POST, environment, grant_s3

from common import path_parameter, request_json, response


def client():
    return boto3.client("s3")


@POST("/objects")
@environment("objects")
@grant_s3("objects", "write")
def put_object(event, context):
    payload, error = request_json(event)
    if error:
        return error
    key = payload.get("key")
    body = payload.get("body")
    if not key or not isinstance(body, str) or body == "":
        return response(400, {"error": "Object key and body are required"})
    try:
        client().put_object(
            Bucket=os.environ["BUCKET_NAME"],
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )
    except Exception:
        return response(502, {"error": "S3 request failed"})
    return response(201, {"key": key})


@GET("/objects/{key}")
@environment("objects")
@grant_s3("objects", "read")
def get_object(event, context):
    key = path_parameter(event, "key")
    if not key:
        return response(400, {"error": "Missing required path parameter"})
    try:
        result = client().get_object(Bucket=os.environ["BUCKET_NAME"], Key=key)
    except Exception as error:
        error_response = getattr(error, "response", {})
        if error_response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            return response(404, {"error": "Object not found"})
        return response(502, {"error": "S3 request failed"})
    return response(200, {"key": key, "body": result["Body"].read().decode("utf-8")})
