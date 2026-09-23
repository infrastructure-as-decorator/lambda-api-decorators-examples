import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[1]
LAYER_PYTHON_DIR = ROOT / "layers" / "orders" / "python"
pytest.importorskip(
    "lambda_api_decorators",
    reason="published lambda-api-decorators is not installed",
)


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
    """Expose the layer exactly as AWS does through /opt/python."""
    table = FakeTable([{"id": "1", "customer": "Ada", "total": 10}])
    monkeypatch.setenv("TABLE_NAME", "Orders-test")
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.syspath_prepend(str(LAYER_PYTHON_DIR))
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(resource=lambda service: FakeResource(table)),
    )
    for module_name in ("orders_shared", "lambdas.orders"):
        sys.modules.pop(module_name, None)

    handlers_module = importlib.import_module("lambdas.orders")
    handlers_module.table = lambda: table
    return table, handlers_module


def invoke(handlers_module, function_name, event):
    result = getattr(handlers_module, function_name)(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    assert isinstance(result["statusCode"], int)
    assert isinstance(result["body"], str)
    return result


def payload(result):
    return json.loads(result["body"])


def test_list_orders_returns_200_and_json_list(handlers):
    table, module = handlers
    result = invoke(module, "list_orders", {})
    assert result["statusCode"] == 200
    assert payload(result) == [{"id": "1", "customer": "Ada", "total": 10}]
    assert table.items["1"]["customer"] == "Ada"


@pytest.mark.parametrize("order_id, status", [("1", 200), ("missing", 404)])
def test_get_order_returns_200_when_present_and_404_when_absent(
    handlers, order_id, status
):
    _table, module = handlers
    result = invoke(module, "get_order", {"pathParameters": {"id": order_id}})
    assert result["statusCode"] == status


def test_create_order_requires_id_stores_object_and_returns_201(handlers):
    table, module = handlers
    order = {"id": "2", "customer": "Lin"}
    result = invoke(module, "create_order", {"body": json.dumps(order)})
    assert result["statusCode"] == 201
    assert payload(result) == order
    assert table.items["2"] == order


def test_update_order_uses_path_id_updates_and_returns_200(handlers):
    table, module = handlers
    result = invoke(
        module,
        "update_order",
        {"pathParameters": {"id": "1"}, "body": json.dumps({"customer": "Grace"})},
    )
    assert result["statusCode"] == 200
    assert payload(result) == {"id": "1", "customer": "Grace"}
    assert table.items["1"] == {"id": "1", "customer": "Grace"}


def test_delete_order_removes_order_and_returns_204(handlers):
    table, module = handlers
    result = invoke(module, "delete_order", {"pathParameters": {"id": "1"}})
    assert result["statusCode"] == 204
    assert "1" not in table.items


@pytest.mark.parametrize(
    "event", [{"body": "not-json"}, {"body": json.dumps({"customer": "Missing id"})}]
)
def test_create_order_invalid_json_or_missing_id_returns_400(handlers, event):
    _table, module = handlers
    assert invoke(module, "create_order", event)["statusCode"] == 400
