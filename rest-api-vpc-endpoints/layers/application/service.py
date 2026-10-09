import repository


class InvalidRequestError(Exception):
    pass


class NotFoundError(Exception):
    pass


class StorageError(Exception):
    pass


def create_item(item):
    if not item.get("id"):
        raise InvalidRequestError("Missing required fields")
    try:
        repository.put_item(item)
    except Exception as error:
        raise StorageError from error
    return item


def get_item(identifier):
    try:
        item = repository.get_item(identifier)
    except Exception as error:
        raise StorageError from error
    if item is None:
        raise NotFoundError
    return item


def put_object(payload):
    key = payload.get("key")
    body = payload.get("body")
    if not key or not isinstance(body, str) or body == "":
        raise InvalidRequestError
    try:
        repository.put_object(key, body)
    except Exception as error:
        raise StorageError from error
    return key


def get_object(key):
    try:
        return repository.get_object(key)
    except Exception as error:
        if getattr(error, "response", {}).get("Error", {}).get("Code") in {
            "NoSuchKey",
            "404",
        }:
            raise NotFoundError from error
        raise StorageError from error
