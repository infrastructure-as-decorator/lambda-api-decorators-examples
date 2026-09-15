import json

from lambda_api_decorators import get


@get("/hello")
def hello(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Hello, world!"}),
    }
