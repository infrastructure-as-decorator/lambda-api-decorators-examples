import ast
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[1]
LAYER_PYTHON = ROOT / "layers" / "application"


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
        self.objects[(Bucket, Key)] = {"Body": Body, "ContentType": ContentType}

    def get_object(self, *, Bucket, Key):
        try:
            stored = self.objects[(Bucket, Key)]
        except KeyError:
            raise FakeClientError("NoSuchKey")
        return {**stored, "Body": SimpleNamespace(read=lambda: stored["Body"])}


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
            assert name == "items-develop"
            return table

    class Client:
        def put_object(self, **kwargs):
            return s3.put_object(**kwargs)

        def get_object(self, **kwargs):
            return s3.get_object(**kwargs)

    monkeypatch.setenv("STAGE", "develop")
    monkeypatch.setenv("BUCKET_NAME", "objects-bucket")
    monkeypatch.delenv("TABLE_NAME", raising=False)
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.syspath_prepend(str(LAYER_PYTHON))
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(
            resource=lambda service: Resource(), client=lambda service: Client()
        ),
    )
    for module_name in (
        "lambdas.items",
        "lambdas.objects",
        "service",
        "repository",
        "common",
    ):
        sys.modules.pop(module_name, None)
    return (
        importlib.import_module("lambdas.items"),
        importlib.import_module("lambdas.objects"),
        importlib.import_module("repository"),
        table,
        s3,
    )


def invoke(handler, event):
    result = handler(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    assert isinstance(result["body"], str)
    return result


def body(result):
    return json.loads(result["body"])


def test_repository_uses_stage_to_derive_table_name(handlers):
    _items, _objects, repository, _table, _s3 = handlers
    assert repository.table_name() == "items-develop"


def test_create_item_parses_and_stores_item(handlers):
    items, _objects, _repository, table, _s3 = handlers
    result = invoke(items.create_item, {"body": '{"id":"1","value":"Ada"}'})
    assert result["statusCode"] == 201
    assert body(result) == {"id": "1", "value": "Ada"}
    assert table.items["1"] == {"id": "1", "value": "Ada"}


@pytest.mark.parametrize(
    "event", [{}, {"body": "not-json"}, {"body": "[]"}, {"body": "{}"}]
)
def test_create_item_rejects_invalid_or_incomplete_request(handlers, event):
    items, _objects, _repository, _table, _s3 = handlers
    assert invoke(items.create_item, event)["statusCode"] == 400


def test_get_item_returns_item_or_not_found(handlers):
    items, _objects, _repository, _table, _s3 = handlers
    invoke(items.create_item, {"body": '{"id":"1","value":"Ada"}'})
    assert body(invoke(items.get_item, {"pathParameters": {"id": "1"}})) == {
        "id": "1",
        "value": "Ada",
    }
    assert invoke(items.get_item, {"pathParameters": {"id": "missing"}})["statusCode"] == 404


def test_item_aws_errors_are_controlled(handlers, monkeypatch):
    items, _objects, repository, _table, _s3 = handlers
    monkeypatch.setattr(
        repository,
        "table",
        lambda: (_ for _ in ()).throw(RuntimeError("down")),
    )
    result = invoke(items.get_item, {"pathParameters": {"id": "1"}})
    assert result["statusCode"] == 502
    assert body(result) == {"error": "DynamoDB request failed"}


def test_put_and_get_object_use_s3(handlers):
    _items, objects, _repository, _table, s3 = handlers
    result = invoke(
        objects.put_object,
        {"body": '{"key":"greeting.txt","body":"hello"}'},
    )
    assert result["statusCode"] == 201
    assert body(result) == {"key": "greeting.txt"}
    assert s3.objects[("objects-bucket", "greeting.txt")]["Body"] == b"hello"
    result = invoke(objects.get_object, {"pathParameters": {"key": "greeting.txt"}})
    assert body(result) == {"key": "greeting.txt", "body": "hello"}


@pytest.mark.parametrize("event", [{}, {"body": ""}, {"body": '{"key":"x"}'}])
def test_put_object_rejects_missing_key_or_body(handlers, event):
    _items, objects, _repository, _table, _s3 = handlers
    assert invoke(objects.put_object, event)["statusCode"] == 400


def test_get_object_returns_not_found(handlers):
    _items, objects, _repository, _table, _s3 = handlers
    result = invoke(objects.get_object, {"pathParameters": {"key": "missing.txt"}})
    assert result["statusCode"] == 404
    assert body(result) == {"error": "Object not found"}


def test_each_handler_has_exactly_one_route_and_uses_the_application_layer():
    for filename, names in {
        "items.py": ("create_item", "get_item"),
        "objects.py": ("put_object", "get_object"),
    }.items():
        source = (ROOT / "lambdas" / filename).read_text()
        tree = ast.parse(source)
        assert '@layer("application")' in source
        for name in names:
            function = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            routes = [
                decorator
                for decorator in function.decorator_list
                if isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Name)
                and decorator.func.id in {"GET", "POST", "DELETE", "PUT", "ANY"}
            ]
            assert len(routes) == 1


def test_layer_contains_common_repository_and_service():
    assert not (ROOT / "layers" / "application" / "python").exists()
    assert {path.name for path in LAYER_PYTHON.glob("*.py")} == {
        "common.py",
        "repository.py",
        "service.py",
    }
