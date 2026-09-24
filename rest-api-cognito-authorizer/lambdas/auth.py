import json

from lambda_api_decorators import GET, public


JSON_HEADERS = {"Content-Type": "application/json"}


@GET("/health")
@public
def health(event, context):
    return {
        "statusCode": 200,
        "headers": JSON_HEADERS,
        "body": json.dumps({"status": "ok"}),
    }


@GET("/me")
def me(event, context):
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims")
    )
    if not isinstance(claims, dict) or not claims.get("sub"):
        return {
            "statusCode": 401,
            "headers": JSON_HEADERS,
            "body": json.dumps({"message": "Unauthorized"}),
        }

    body = {"sub": claims["sub"]}
    if claims.get("cognito:username"):
        body["username"] = claims["cognito:username"]
    return {
        "statusCode": 200,
        "headers": JSON_HEADERS,
        "body": json.dumps(body),
    }
