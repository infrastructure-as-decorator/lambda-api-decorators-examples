import os

import boto3


def stage():
    return os.environ["STAGE"]


def table_name():
    return f"items-{stage()}"


def table():
    return boto3.resource("dynamodb").Table(table_name())


def put_item(item):
    table().put_item(Item=item)


def get_item(identifier):
    return table().get_item(Key={"id": identifier}).get("Item")


def bucket_name():
    return os.environ["BUCKET_NAME"]


def put_object(key, body):
    boto3.client("s3").put_object(
        Bucket=bucket_name(),
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )


def get_object(key):
    return boto3.client("s3").get_object(Bucket=bucket_name(), Key=key)[
        "Body"
    ].read().decode("utf-8")
