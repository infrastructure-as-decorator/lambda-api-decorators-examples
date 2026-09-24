import json

from lambda_api_decorators import CurrentUserError, GET, current_user, public


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
    try:
        user = current_user(event)
    except CurrentUserError:
        return {
            "statusCode": 401,
            "headers": JSON_HEADERS,
            "body": json.dumps({"message": "Unauthorized"}),
        }

    body = {"sub": user.subject}
    if user.username is not None:
        body["username"] = user.username
    return {
        "statusCode": 200,
        "headers": JSON_HEADERS,
        "body": json.dumps(body),
    }
