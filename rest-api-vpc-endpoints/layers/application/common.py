import json


JSON_HEADERS = {"Content-Type": "application/json"}


def response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload),
    }


def request_json(event):
    try:
        value = json.loads(event.get("body") or "")
    except (TypeError, json.JSONDecodeError):
        return None, response(400, {"error": "Invalid JSON body"})
    if not isinstance(value, dict):
        return None, response(400, {"error": "JSON body must be an object"})
    return value, None


def path_parameter(event, name):
    return (event.get("pathParameters") or {}).get(name)
