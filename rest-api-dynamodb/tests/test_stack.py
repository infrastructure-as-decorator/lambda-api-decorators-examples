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
pytest.importorskip("lambda_api_decorators_cdk", reason="published lambda-api-decorators-cdk is not installed")

import aws_cdk as cdk
from aws_cdk.assertions import Template

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
DOCKER_AVAILABLE = bool(shutil.which("docker")) and subprocess.run(
    ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
).returncode == 0


def synthesized(monkeypatch):
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is unavailable for CDK PythonFunction bundling")
    monkeypatch.chdir(ROOT)
    from rest_api_dynamodb.rest_api_dynamodb_stack import RestApiDynamodbStack

    return Template.from_stack(RestApiDynamodbStack(cdk.App(), "TestRestApiDynamodbStack"))


def test_stack_has_real_table_rest_api_five_lambdas_and_destroy_policy(monkeypatch):
    template = synthesized(monkeypatch)
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::DynamoDB::Table", 1)
    template.resource_count_is("AWS::Lambda::Function", 5)
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "BillingMode": "PAY_PER_REQUEST",
        "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
        "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
    })
    template.has_resource("AWS::DynamoDB::Table", {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"})


def test_template_contains_the_five_required_methods_and_paths(monkeypatch):
    template = synthesized(monkeypatch)
    methods = template.find_resources("AWS::ApiGateway::Method")
    assert len(methods) == 5
    assert {method["Properties"]["HttpMethod"] for method in methods.values()} == {"GET", "POST", "PUT", "DELETE"}
    resources = template.find_resources("AWS::ApiGateway::Resource")
    assert {resource["Properties"].get("PathPart") for resource in resources.values()} >= {"orders", "{id}"}


def test_default_and_post_lambda_configuration(monkeypatch):
    template = synthesized(monkeypatch)
    functions = template.find_resources("AWS::Lambda::Function")
    assert sum(resource["Properties"].get("Runtime") == "python3.14" for resource in functions.values()) == 4
    configured = [resource for resource in functions.values() if resource["Properties"].get("FunctionName") == "configured-handler"]
    assert len(configured) == 1
    properties = configured[0]["Properties"]
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


def test_each_handler_has_exactly_one_http_decorator():
    http_names = {"GET", "POST", "PUT", "DELETE", "ANY"}
    for source in (ROOT / "lambdas").glob("*.py"):
        if source.name.startswith("__") or source.name == "orders.py":
            continue
        tree = ast.parse(source.read_text(), filename=str(source))
        handlers = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "lambda_handler"]
        assert len(handlers) == 1, source
        decorators = [decorator for decorator in handlers[0].decorator_list if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) and decorator.func.id in http_names]
        assert len(decorators) == 1, source


def test_post_decorator_contract_is_exact():
    tree = ast.parse((ROOT / "lambdas" / "create_order.py").read_text())
    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "lambda_handler")
    actual = []
    for decorator in handler.decorator_list:
        assert isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name)
        actual.append(ast.unparse(decorator))
    assert actual == [
        'POST("/orders")', 'grant_dynamodb("orders", "write")', "memory_size(1024)", "timeout(15)",
        'environment("STAGE", "TABLE_NAME")', 'runtime("python3.12")', 'role("api-role")',
        'description("Configured endpoint")', 'name("configured-handler")',
    ]


def test_stack_uses_named_registries_and_no_shared_default_role():
    source = (ROOT / "rest_api_dynamodb" / "rest_api_dynamodb_stack.py").read_text()
    for name in ("default_runtime", "common_environment", "environment_registry", "role_registry", "dynamodb_table_registry"):
        assert name in source
    assert "default_role" not in source


def test_requirements_are_pinned_and_do_not_use_git_path_or_editable():
    cdk_requirements = (ROOT / "requirements.txt").read_text().splitlines()
    lambda_requirements = (ROOT / "lambdas" / "requirements.txt").read_text().splitlines()
    assert "aws-cdk-lib" in "\n".join(cdk_requirements)
    assert "constructs" in "\n".join(cdk_requirements)
    assert "lambda-api-decorators-cdk==0.4.4" in cdk_requirements
    assert "lambda-api-decorators" not in cdk_requirements
    assert "lambda-api-decorators==0.3.2" in lambda_requirements
    assert not any(any(token in line for token in ("git+", "-e ", "file:", "path:")) for line in cdk_requirements + lambda_requirements)


def test_no_generated_artifacts_are_tracked():
    tracked = subprocess.check_output(["git", "ls-files", str(ROOT)], text=True).splitlines()
    assert not [path for path in tracked if any(part in path.split("/") for part in ("cdk.out", "__pycache__", ".pytest_cache"))]
