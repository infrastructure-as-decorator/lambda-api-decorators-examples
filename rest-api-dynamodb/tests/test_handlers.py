import importlib
import json
import sys
from types import SimpleNamespace
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "lambdas"))

import pytest


class FakeTable:
    def __init__(self, items=None):
        self.items = {item["id"]: dict(item) for item in (items or [])}
        self.last_key = None

    def scan(self):
        return {"Items": list(self.items.values())}

    def get_item(self, *, Key):
        self.last_key = Key
        item = self.items.get(Key["id"])
        return {} if item is None else {"Item": item}

    def put_item(self, *, Item, **kwargs):
        self.items[Item["id"]] = dict(Item)

    def delete_item(self, *, Key, **kwargs):
        item = self.items.pop(Key["id"], None)
        return {} if item is None else {"Attributes": item}


@pytest.fixture
def handlers(monkeypatch):
    table = FakeTable([{"id": "1", "customer": "Ada", "total": 10, "status": "new"}])
    monkeypatch.setenv("TABLE_NAME", "Orders-test")
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setitem(
        sys.modules, "boto3", SimpleNamespace(resource=lambda service: FakeResource(table))
    )
    sys.modules.pop("lambdas.orders", None)
    orders = importlib.import_module("orders")
    return table, orders


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        assert name == "Orders-test"
        return self._table


def invoke(module_name, event, handlers):
    module = importlib.import_module(module_name)
    result = module.lambda_handler(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    return result


def body(result):
    return json.loads(result["body"])


def test_list_orders_returns_proxy_response_and_uses_table_name(handlers):
    result = invoke("list_orders", {}, handlers)
    assert result["statusCode"] == 200
    assert body(result) == [{"id": "1", "customer": "Ada", "total": 10, "status": "new"}]


def test_get_existing_and_missing_orders(handlers):
    event = {"pathParameters": {"order_id": "1"}}
    assert invoke("get_order", event, handlers)["statusCode"] == 200
    missing = invoke("get_order", {"pathParameters": {"order_id": "404"}}, handlers)
    assert missing["statusCode"] == 404
    assert body(missing) == {"error": "Order not found"}


def test_create_valid_order(handlers):
    event = {"body": json.dumps({"id": "2", "customer": "Lin", "total": 20, "status": "new"})}
    result = invoke("create_order", event, handlers)
    assert result["statusCode"] == 201
    assert body(result)["id"] == "2"


@pytest.mark.parametrize(
    "payload, expected_fields",
    [("not-json", None), ({"id": "2", "customer": "Lin"}, ["total", "status"])],
)
def test_create_validates_json_and_required_fields(payload, expected_fields, handlers):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    result = invoke("create_order", {"body": raw}, handlers)
    assert result["statusCode"] == 400
    if expected_fields is None:
        assert body(result) == {"error": "Invalid JSON body"}
    else:
        assert body(result)["fields"] == expected_fields


def test_update_existing_and_missing_orders(handlers):
    event = {
        "pathParameters": {"order_id": "1"},
        "body": json.dumps({"customer": "Ada", "total": 11, "status": "paid"}),
    }
    result = invoke("update_order", event, handlers)
    assert result["statusCode"] == 200
    assert body(result)["total"] == 11
    missing = invoke(
        "update_order",
        {"pathParameters": {"order_id": "404"}, "body": json.dumps({"customer": "A", "total": 1, "status": "new"})},
        handlers,
    )
    assert missing["statusCode"] == 404


def test_delete_existing_and_missing_orders(handlers):
    result = invoke("delete_order", {"pathParameters": {"order_id": "1"}}, handlers)
    assert result["statusCode"] == 200
    missing = invoke("delete_order", {"pathParameters": {"order_id": "1"}}, handlers)
    assert missing["statusCode"] == 404
