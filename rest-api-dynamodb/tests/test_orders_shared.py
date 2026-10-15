import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).parents[1]
LAYER_DIR = ROOT / "layers" / "orders"
pytest.importorskip(
    "lambda_api_decorators",
    reason="published lambda-api-decorators is not installed",
)


def client_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "DynamoDB operation failed"}},
        "PutItem",
    )


class FakeTable:
    def __init__(self, error=None):
        self.error = error
        self.put_calls = []
        self.read_called = False

    def put_item(self, **kwargs):
        self.put_calls.append(kwargs)
        if self.error:
            raise self.error

    def get_item(self, **kwargs):
        self.read_called = True
        raise AssertionError("create_order_record must not perform a preliminary read")


@pytest.fixture
def shared(monkeypatch):
    monkeypatch.setenv("STAGE", "test")
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.syspath_prepend(str(LAYER_DIR))

    table = FakeTable()
    tables = [table]

    def resource(_service):
        return SimpleNamespace(Table=lambda _name: table)

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(resource=resource))
    sys.modules.pop("orders_shared", None)
    module = importlib.import_module("orders_shared")
    return module, tables


def test_successful_conditional_write_uses_expected_expression(shared):
    module, tables = shared
    order = {"id": "1", "customer": "Ada"}

    module.create_order_record(order)

    assert tables[0].put_calls == [
        {"Item": order, "ConditionExpression": "attribute_not_exists(id)"}
    ]
    assert not tables[0].read_called


def test_conditional_failure_becomes_order_already_exists_and_preserves_cause(
    shared,
):
    module, tables = shared
    error = client_error("ConditionalCheckFailedException")
    tables[0].error = error

    with pytest.raises(module.OrderAlreadyExists) as raised:
        module.create_order_record({"id": "1"})

    assert raised.value.__cause__ is error
    assert not tables[0].read_called


def test_other_client_errors_propagate_unchanged(shared):
    module, tables = shared
    error = client_error("ProvisionedThroughputExceededException")
    tables[0].error = error

    with pytest.raises(ClientError) as raised:
        module.create_order_record({"id": "1"})

    assert raised.value is error
    assert not tables[0].read_called
