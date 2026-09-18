import json
import os

import boto3


JSON_HEADERS = {"Content-Type": "application/json"}
REQUIRED_FIELDS = ("customer", "total", "status")


def table():
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload),
    }


def request_json(event):
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, json.JSONDecodeError):
        return None, response(400, {"error": "Invalid JSON body"})
    if not isinstance(body, dict):
        return None, response(400, {"error": "JSON body must be an object"})
    return body, None


def order_id(event):
    return (event.get("pathParameters") or {}).get("order_id")


def missing_fields(order):
    return [field for field in REQUIRED_FIELDS if field not in order]
