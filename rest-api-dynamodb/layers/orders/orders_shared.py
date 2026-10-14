import json
import os
from decimal import Decimal

import boto3


JSON_HEADERS = {"Content-Type": "application/json"}
REQUIRED_FIELDS = ("customer", "total", "status")
DEFAULT_STAGE = "dev"


def table_name():
    stage = os.environ.get("STAGE", DEFAULT_STAGE)
    return f"{stage}-orders"


def table():
    return boto3.resource("dynamodb").Table(table_name())


def list_order_records():
    return table().scan().get("Items", [])


def find_order(order_id):
    return table().get_item(Key={"id": order_id}).get("Item")


def create_order_record(order):
    table().put_item(Item=order, ConditionExpression="attribute_not_exists(id)")


def update_order_record(order_id, order):
    updated = {"id": order_id, **order}
    table().put_item(Item=updated)
    return updated


def delete_order_record(order_id):
    return table().delete_item(
        Key={"id": order_id}, ReturnValues="ALL_OLD"
    ).get("Attributes")


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": ""
        if status_code == 204
        else json.dumps(payload, default=json_default),
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
    return (event.get("pathParameters") or {}).get("id")


def missing_fields(order):
    return [field for field in REQUIRED_FIELDS if field not in order]
