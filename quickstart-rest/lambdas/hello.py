import json

from lambda_api_decorators import GET


@GET("/hello")
def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Hello, world!"}),
    }
