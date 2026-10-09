import importlib
import json
import sys
import ast
from types import SimpleNamespace
from pathlib import Path

import pytest


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, *, Item):
        self.items[Item["id"]] = dict(Item)

    def get_item(self, *, Key):
        item = self.items.get(Key["id"])
        return {} if item is None else {"Item": dict(item)}


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "ContentType": ContentType,
        }

    def get_object(self, *, Bucket, Key):
        try:
            stored = self.objects[(Bucket, Key)]
        except KeyError:
            error = SimpleNamespace(response={"Error": {"Code": "NoSuchKey"}})
            raise error
        return {"Body": SimpleNamespace(read=lambda: stored["Body"]), **stored}


class FakeClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


@pytest.fixture
def handlers(monkeypatch):
    table = FakeTable()
    s3 = FakeS3()

    class Resource:
        def Table(self, name):
            assert name == "items-table"
            return table

    class Client:
        def put_object(self, **kwargs):
            return s3.put_object(**kwargs)

        def get_object(self, **kwargs):
            return s3.get_object(**kwargs)

    monkeypatch.setenv("TABLE_NAME", "items-table")
    monkeypatch.setenv("BUCKET_NAME", "objects-bucket")
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(resource=lambda service: Resource(), client=lambda service: Client()),
    )
    for module_name in ("lambdas.items", "lambdas.objects"):
        sys.modules.pop(module_name, None)
    return importlib.import_module("lambdas.items"), importlib.import_module("lambdas.objects"), table, s3


def invoke(handler, event):
    result = handler(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    assert isinstance(result["body"], str)
    return result


def body(result):
    return json.loads(result["body"])


def test_create_item_parses_and_stores_item(handlers):
    items, _objects, table, _s3 = handlers
    result = invoke(items.create_item, {"body": '{"id":"1","value":"Ada"}'})
    assert result["statusCode"] == 201
    assert body(result) == {"id": "1", "value": "Ada"}
    assert table.items["1"] == {"id": "1", "value": "Ada"}


@pytest.mark.parametrize(
    "event", [{}, {"body": "not-json"}, {"body": "[]"}, {"body": "{}"}]
)
def test_create_item_rejects_invalid_or_incomplete_request(handlers, event):
    items, _objects, _table, _s3 = handlers
    assert invoke(items.create_item, event)["statusCode"] == 400


def test_get_item_returns_item_or_not_found(handlers):
    items, _objects, _table, _s3 = handlers
    invoke(items.create_item, {"body": '{"id":"1","value":"Ada"}'})
    assert body(invoke(items.get_item, {"pathParameters": {"id": "1"}})) == {
        "id": "1",
        "value": "Ada",
    }
    assert invoke(items.get_item, {"pathParameters": {"id": "missing"}})["statusCode"] == 404


def test_item_aws_errors_are_controlled(handlers, monkeypatch):
    items, _objects, _table, _s3 = handlers
    monkeypatch.setattr(items, "table", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    result = invoke(items.get_item, {"pathParameters": {"id": "1"}})
    assert result["statusCode"] == 502
    assert body(result) == {"error": "DynamoDB request failed"}


def test_put_and_get_object_use_s3(handlers):
    _items, objects, _table, s3 = handlers
    result = invoke(
        objects.put_object,
        {"pathParameters": {"key": "greeting.txt"}, "body": "hello"},
    )
    assert result["statusCode"] == 201
    assert body(result) == {"key": "greeting.txt"}
    assert s3.objects[("objects-bucket", "greeting.txt")]["Body"] == b"hello"
    result = invoke(objects.get_object, {"pathParameters": {"key": "greeting.txt"}})
    assert body(result) == {"key": "greeting.txt", "body": "hello"}


@pytest.mark.parametrize("event", [{}, {"body": ""}])
def test_put_object_rejects_missing_key_or_body(handlers, event):
    _items, objects, _table, _s3 = handlers
    assert invoke(objects.put_object, event)["statusCode"] == 400


def test_get_object_returns_not_found(handlers):
    _items, objects, _table, _s3 = handlers
    result = invoke(objects.get_object, {"pathParameters": {"key": "missing.txt"}})
    assert result["statusCode"] == 404
    assert body(result) == {"error": "Object not found"}


def test_each_handler_has_exactly_one_route():
    root = Path(__file__).parents[1]
    for filename, names in {
        "items.py": ("create_item", "get_item"),
        "objects.py": ("put_object", "get_object"),
    }.items():
        tree = ast.parse((root / "lambdas" / filename).read_text())
        for name in names:
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
            routes = [
                decorator for decorator in function.decorator_list
                if isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id in {"GET", "POST", "PUT", "DELETE", "ANY"}
            ]
            assert len(routes) == 1
