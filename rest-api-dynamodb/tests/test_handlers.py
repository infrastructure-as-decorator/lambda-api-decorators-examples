import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

LAMBDA_DIR = Path(__file__).parents[1] / "lambdas"
sys.path.insert(0, str(LAMBDA_DIR))
pytest.importorskip("lambda_api_decorators", reason="published lambda-api-decorators is not installed")


class FakeTable:
    def __init__(self, items=()):
        self.items = {item["id"]: dict(item) for item in items}

    def scan(self):
        return {"Items": list(self.items.values())}

    def get_item(self, *, Key):
        item = self.items.get(Key["id"])
        return {} if item is None else {"Item": dict(item)}

    def put_item(self, *, Item, **kwargs):
        self.items[Item["id"]] = dict(Item)

    def delete_item(self, *, Key, **kwargs):
        item = self.items.pop(Key["id"], None)
        return {} if item is None else {"Attributes": item}


class FakeResource:
    def __init__(self, table):
        self.table_value = table

    def Table(self, name):
        assert name == "Orders-test"
        return self.table_value


@pytest.fixture
def handlers(monkeypatch):
    table = FakeTable([{"id": "1", "customer": "Ada", "total": 10}])
    monkeypatch.setenv("TABLE_NAME", "Orders-test")
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(resource=lambda service: FakeResource(table)))
    for module_name in ("orders", "list_orders", "get_order", "create_order", "update_order", "delete_order"):
        sys.modules.pop(module_name, None)
    return table


def invoke(module_name, event):
    result = importlib.import_module(module_name).lambda_handler(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    assert isinstance(result["statusCode"], int)
    assert isinstance(result["body"], str)
    return result


def payload(result):
    return json.loads(result["body"])


def test_get_orders_returns_200_and_json_list(handlers):
    result = invoke("list_orders", {})
    assert result["statusCode"] == 200
    assert payload(result) == [{"id": "1", "customer": "Ada", "total": 10}]


@pytest.mark.parametrize("order_id, status", [("1", 200), ("missing", 404)])
def test_get_order_returns_200_when_present_and_404_when_absent(handlers, order_id, status):
    result = invoke("get_order", {"pathParameters": {"id": order_id}})
    assert result["statusCode"] == status


def test_post_requires_id_stores_object_and_returns_201(handlers):
    order = {"id": "2", "customer": "Lin"}
    result = invoke("create_order", {"body": json.dumps(order)})
    assert result["statusCode"] == 201
    assert payload(result) == order
    assert handlers.items["2"] == order


def test_put_uses_path_id_updates_and_returns_200(handlers):
    result = invoke("update_order", {"pathParameters": {"id": "1"}, "body": json.dumps({"customer": "Grace"})})
    assert result["statusCode"] == 200
    assert payload(result) == {"id": "1", "customer": "Grace"}
    assert handlers.items["1"] == {"id": "1", "customer": "Grace"}


def test_delete_removes_order_and_returns_204(handlers):
    result = invoke("delete_order", {"pathParameters": {"id": "1"}})
    assert result["statusCode"] == 204
    assert "1" not in handlers.items


@pytest.mark.parametrize("event", [{"body": "not-json"}, {"body": json.dumps({"customer": "Missing id"})}])
def test_post_invalid_json_or_missing_id_returns_400(handlers, event):
    assert invoke("create_order", event)["statusCode"] == 400
