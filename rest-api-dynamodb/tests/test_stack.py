import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JSII_RUNTIME_PACKAGE_CACHE", "/tmp/codex-jsii-cache")

pytest.importorskip("aws_cdk", reason="aws-cdk-lib is not installed")
pytest.importorskip("constructs", reason="constructs is not installed")
pytest.importorskip(
    "lambda_api_decorators_cdk",
    reason="published lambda-api-decorators-cdk is not installed",
)

import aws_cdk as cdk
from aws_cdk.assertions import Template


ROOT = Path(__file__).parents[1]
LAMBDA_DIR = ROOT / "lambdas"
LAYER_DIR = ROOT / "layers" / "orders"
LAYER_PYTHON_DIR = LAYER_DIR / "python"
DOCKER_AVAILABLE = bool(shutil.which("docker")) and subprocess.run(
    ["docker", "info"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=False,
).returncode == 0

HTTP_DECORATORS = {"GET", "POST", "PUT", "DELETE", "ANY"}
EXPECTED_ROUTES = {
    "list_orders": ("GET", "/orders"),
    "get_order": ("GET", "/orders/{id}"),
    "create_order": ("POST", "/orders"),
    "update_order": ("PUT", "/orders/{id}"),
    "delete_order": ("DELETE", "/orders/{id}"),
}
EXPECTED_HELPERS = {
    "JSON_HEADERS",
    "REQUIRED_FIELDS",
    "table",
    "response",
    "request_json",
    "order_id",
    "missing_fields",
}


def parse(path):
    return ast.parse(path.read_text(), filename=str(path))


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    return None


def decorator_calls(function):
    return [
        decorator
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call)
    ]


def route_decorators(function):
    return [
        decorator
        for decorator in decorator_calls(function)
        if call_name(decorator.func) in HTTP_DECORATORS
    ]


def layer_decorators(function):
    return [
        decorator
        for decorator in decorator_calls(function)
        if call_name(decorator.func) == "layer"
    ]


def handler_functions(tree):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def decorator_signature(node):
    return (
        call_name(node.func),
        tuple(argument.value for argument in node.args),
        tuple((keyword.arg, keyword.value.value) for keyword in node.keywords),
    )


def synthesized(monkeypatch):
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is unavailable for CDK PythonFunction bundling")
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.chdir(ROOT)
    from rest_api_dynamodb.rest_api_dynamodb_stack import RestApiDynamodbStack

    return Template.from_stack(RestApiDynamodbStack(cdk.App(), "TestRestApiDynamodbStack"))


def test_lambdas_are_grouped_in_one_orders_module():
    assert sorted(path.name for path in LAMBDA_DIR.glob("*.py") if path.name != "__init__.py") == [
        "orders.py"
    ]
    assert (LAMBDA_DIR / "orders.py").is_file()
    for old_name in (
        "create_order.py",
        "delete_order.py",
        "get_order.py",
        "list_orders.py",
        "update_order.py",
    ):
        assert not (LAMBDA_DIR / old_name).exists()


def test_layer_uses_python_import_root_and_contains_only_shared_helpers():
    source = LAYER_PYTHON_DIR / "orders_shared.py"
    assert source.is_file()
    assert (LAYER_DIR / "requirements.txt").is_file()

    tree = parse(source)
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    names.update(
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    )
    assert names == EXPECTED_HELPERS

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in EXPECTED_ROUTES
        for node in tree.body
    )
    assert not any(
        call_name(node.func) in HTTP_DECORATORS
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )


def test_orders_module_has_five_handlers_one_route_and_one_registered_layer():
    source = LAMBDA_DIR / "orders.py"
    tree = parse(source)
    functions = handler_functions(tree)
    assert set(functions) == set(EXPECTED_ROUTES)

    for name, (method, path) in EXPECTED_ROUTES.items():
        routes = route_decorators(functions[name])
        assert len(routes) == 1
        assert decorator_signature(routes[0]) == (method, (path,), ())
        layers = layer_decorators(functions[name])
        assert len(layers) == 1
        assert decorator_signature(layers[0]) == ("layer", ("orders",), ())


def test_orders_module_imports_helpers_from_layer():
    tree = parse(LAMBDA_DIR / "orders.py")
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert any(
        node.module == "orders_shared"
        and {alias.name for alias in node.names}
        >= {"order_id", "request_json", "response", "table"}
        for node in imports
    )


def test_stack_declares_layer_path_and_the_grouped_module():
    source = (ROOT / "rest_api_dynamodb" / "rest_api_dynamodb_stack.py").read_text()
    assert "lambda_path=\"lambdas\"" in source
    assert "layers_path=\"layers\"" in source


def test_post_decorator_contract_is_exact_except_for_layer_selection():
    tree = parse(LAMBDA_DIR / "orders.py")
    handler = handler_functions(tree)["create_order"]
    actual = [
        decorator_signature(decorator)
        for decorator in decorator_calls(handler)
        if call_name(decorator.func) != "layer"
    ]
    assert actual == [
        ("POST", ("/orders",), ()),
        ("grant_dynamodb", ("orders", "write"), ()),
        ("memory_size", (1024,), ()),
        ("timeout", (15,), ()),
        ("environment", ("STAGE", "TABLE_NAME"), ()),
        ("runtime", ("python3.12",), ()),
        ("role", ("api-role",), ()),
        ("description", ("Configured endpoint",), ()),
        ("name", ("configured-handler",), ()),
    ]


def test_stack_has_real_table_rest_api_five_lambdas_layer_and_destroy_policy(monkeypatch):
    template = synthesized(monkeypatch)
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.resource_count_is("AWS::Lambda::Function", 5)
    template.resource_count_is("AWS::Lambda::LayerVersion", 1)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        },
    )
    template.has_resource(
        "AWS::DynamoDB::Table",
        {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"},
    )


def test_every_lambda_references_the_orders_layer(monkeypatch):
    template = synthesized(monkeypatch)
    layer_id = next(iter(template.find_resources("AWS::Lambda::LayerVersion")))
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == 5
    assert all(
        layer_id in json.dumps(resource["Properties"].get("Layers", []))
        for resource in functions.values()
    )


def test_template_contains_five_methods_and_expected_paths(monkeypatch):
    template = synthesized(monkeypatch)
    methods = template.find_resources("AWS::ApiGateway::Method")
    assert len(methods) == 5
    assert {method["Properties"]["HttpMethod"] for method in methods.values()} == {
        "GET",
        "POST",
        "PUT",
        "DELETE",
    }
    resources = template.find_resources("AWS::ApiGateway::Resource")
    assert {resource["Properties"].get("PathPart") for resource in resources.values()} >= {
        "orders",
        "{id}",
    }


def test_five_lambda_handlers_are_distinct_functions_in_orders_module(monkeypatch):
    template = synthesized(monkeypatch)
    handlers = {
        resource["Properties"]["Handler"]
        for resource in template.find_resources("AWS::Lambda::Function").values()
    }
    assert handlers == {
        "orders.list_orders",
        "orders.get_order",
        "orders.create_order",
        "orders.update_order",
        "orders.delete_order",
    }


def test_default_and_post_lambda_configuration(monkeypatch):
    template = synthesized(monkeypatch)
    functions = template.find_resources("AWS::Lambda::Function")
    assert sum(resource["Properties"].get("Runtime") == "python3.14" for resource in functions.values()) == 4
    configured = [
        resource
        for resource in functions.values()
        if resource["Properties"].get("FunctionName") == "configured-handler"
    ]
    assert len(configured) == 1
    properties = configured[0]["Properties"]
    assert properties["Handler"] == "orders.create_order"
    assert properties["Runtime"] == "python3.12"
    assert properties["MemorySize"] == 1024
    assert properties["Timeout"] == 15
    assert properties["Description"] == "Configured endpoint"
    assert set(properties["Environment"]["Variables"]) >= {"STAGE", "TABLE_NAME"}
    assert properties["Role"]["Fn::GetAtt"][0].startswith("ApiRole")


def test_dynamodb_permissions_reference_the_table(monkeypatch):
    template = synthesized(monkeypatch)
    table_logical_id = next(iter(template.find_resources("AWS::DynamoDB::Table")))
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [
        statement
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        if "dynamodb:" in json.dumps(statement.get("Action", []))
    ]
    assert statements
    assert all(table_logical_id in json.dumps(statement["Resource"]) for statement in statements)


def test_stack_uses_named_registries_and_no_shared_default_role():
    source = (ROOT / "rest_api_dynamodb" / "rest_api_dynamodb_stack.py").read_text()
    for name in (
        "default_runtime",
        "common_environment",
        "environment_registry",
        "role_registry",
        "dynamodb_table_registry",
    ):
        assert name in source
    assert "default_role" not in source


def test_no_generated_artifacts_are_tracked():
    tracked = subprocess.check_output(["git", "ls-files", str(ROOT)], text=True).splitlines()
    assert not [
        path
        for path in tracked
        if any(part in path.split("/") for part in ("cdk.out", "__pycache__", ".pytest_cache"))
    ]
