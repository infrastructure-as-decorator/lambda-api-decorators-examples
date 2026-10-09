import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
STACK_SOURCE = ROOT / "rest_api_vpc_endpoints" / "rest_api_vpc_endpoints_stack.py"
DOCKER_AVAILABLE = bool(shutil.which("docker")) and subprocess.run(
    ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
).returncode == 0


def stack_template(monkeypatch):
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is unavailable for CDK PythonFunction bundling")
    os.environ.setdefault("JSII_RUNTIME_PACKAGE_CACHE", "/tmp/codex-jsii-cache")
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.chdir(ROOT)
    from aws_cdk import App
    from aws_cdk.assertions import Template
    from rest_api_vpc_endpoints.rest_api_vpc_endpoints_stack import RestApiVpcEndpointsStack

    stack = RestApiVpcEndpointsStack(App(), "TestRestApiVpcEndpointsStack")
    template = Template.from_stack(stack)
    template._test_stack = stack
    return template


def resources(template, resource_type):
    return template.find_resources(resource_type)


def refs(value, logical_id):
    return logical_id in json.dumps(value)


def api_paths(template):
    resource_map = resources(template, "AWS::ApiGateway::Resource")
    paths = {}
    unresolved = dict(resource_map)
    while unresolved:
        progressed = False
        for logical_id, resource in list(unresolved.items()):
            parent = resource["Properties"]["ParentId"]
            parent_id = parent.get("Ref") if isinstance(parent, dict) else None
            if parent_id and parent_id in paths:
                paths[logical_id] = f"{paths[parent_id]}/{resource['Properties']['PathPart']}"
                del unresolved[logical_id]
                progressed = True
            elif isinstance(parent, dict) and "Fn::GetAtt" in parent:
                paths[logical_id] = f"/{resource['Properties']['PathPart']}"
                del unresolved[logical_id]
                progressed = True
        if not progressed:
            raise AssertionError(f"unresolved API resources: {unresolved}")
    return paths


def test_source_uses_published_registries_and_current_vpc_selection_contract():
    source = STACK_SOURCE.read_text()
    tree = ast.parse(source)
    config = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "LambdaApiConfig"
    )
    keywords = {keyword.arg for keyword in config.keywords}
    assert {"vpc_registry", "dynamodb_table_registry", "s3_bucket_registry", "environment_registry"} <= keywords
    assert "vpc_subnets" in source
    assert "PRIVATE_ISOLATED" in source
    assert 'table_name = f"items-{stage}"' in source
    assert "table_name=table_name" in source
    assert '"stage": {"STAGE": stage}' in source
    assert '"TABLE_NAME"' not in source
    assert 'layers_path="layers"' in source


def test_network_has_one_vpc_no_nat_and_two_gateway_endpoints(monkeypatch):
    template = stack_template(monkeypatch)
    template.resource_count_is("AWS::EC2::VPC", 1)
    assert resources(template, "AWS::EC2::NatGateway") == {}
    template.resource_count_is("AWS::EC2::VPCEndpoint", 2)
    endpoints = resources(template, "AWS::EC2::VPCEndpoint").values()
    services = [
        json.dumps(endpoint["Properties"]["ServiceName"], sort_keys=True).lower()
        for endpoint in endpoints
    ]
    assert any("dynamodb" in service for service in services)
    assert any('"s3"' in service or ".s3" in service for service in services)
    for endpoint in endpoints:
        assert endpoint["Properties"]["VpcEndpointType"] == "Gateway"
        assert endpoint["Properties"].get("RouteTableIds")


def test_vpc_uses_isolated_subnets_and_lambdas_use_them(monkeypatch):
    template = stack_template(monkeypatch)
    subnets = resources(template, "AWS::EC2::Subnet")
    assert len(subnets) >= 2
    route_tables = resources(template, "AWS::EC2::RouteTable")
    assert len(route_tables) >= 2
    functions = [
        resource for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler") in {
            "items.create_item", "items.get_item", "objects.put_object", "objects.get_object"
        }
    ]
    assert len(functions) == 4
    for function in functions:
        assert function["Properties"]["VpcConfig"]["SubnetIds"]
        assert function["Properties"]["VpcConfig"]["SecurityGroupIds"]


def test_table_name_and_lambda_environment_use_the_stage(monkeypatch):
    template = stack_template(monkeypatch)
    table = next(iter(resources(template, "AWS::DynamoDB::Table").values()))
    assert table["Properties"]["TableName"] == "items-develop"
    functions = [
        resource for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler") in {
            "items.create_item", "items.get_item", "objects.put_object", "objects.get_object"
        }
    ]
    assert len(functions) == 4
    for function in functions:
        variables = function["Properties"]["Environment"]["Variables"]
        assert variables["STAGE"] == "develop"
        assert "TABLE_NAME" not in variables


def test_application_layer_is_attached_to_each_handler(monkeypatch):
    template = stack_template(monkeypatch)
    layers = resources(template, "AWS::Lambda::LayerVersion")
    assert len(layers) == 1
    layer_id = next(iter(layers))
    functions = [
        resource for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler") in {
            "items.create_item", "items.get_item", "objects.put_object", "objects.get_object"
        }
    ]
    assert all(layer_id in json.dumps(function["Properties"]["Layers"]) for function in functions)


def test_four_application_lambdas_have_distinct_roles_and_handlers(monkeypatch):
    template = stack_template(monkeypatch)
    functions = {
        resource["Properties"]["Handler"]: resource
        for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler")
        in {"items.create_item", "items.get_item", "objects.put_object", "objects.get_object"}
    }
    assert set(functions) == {"items.create_item", "items.get_item", "objects.put_object", "objects.get_object"}
    roles = {json.dumps(function["Properties"]["Role"]) for function in functions.values()}
    assert len(roles) == 4


def test_resources_are_destroyable_and_api_has_expected_routes(monkeypatch):
    template = stack_template(monkeypatch)
    table_id = next(iter(resources(template, "AWS::DynamoDB::Table")))
    table = resources(template, "AWS::DynamoDB::Table")[table_id]
    assert table["DeletionPolicy"] == "Delete"
    bucket = next(iter(resources(template, "AWS::S3::Bucket").values()))
    assert bucket["DeletionPolicy"] == "Delete"
    assert bucket["UpdateReplacePolicy"] == "Delete"
    methods = resources(template, "AWS::ApiGateway::Method")
    paths = api_paths(template)
    routes = {
        (method["Properties"]["HttpMethod"], paths[method["Properties"]["ResourceId"]["Ref"]])
        for method in methods.values()
    }
    assert routes == {
        ("POST", "/items"), ("GET", "/items/{id}"),
        ("POST", "/objects"), ("GET", "/objects/{key}"),
    }


def test_grants_are_scoped_to_the_registered_resources(monkeypatch):
    template = stack_template(monkeypatch)
    table_id = next(iter(resources(template, "AWS::DynamoDB::Table")))
    bucket_id = next(iter(resources(template, "AWS::S3::Bucket")))
    policies = resources(template, "AWS::IAM::Policy")
    application_policies = [
        policy for policy in policies.values()
        if table_id in json.dumps(policy) or bucket_id in json.dumps(policy)
    ]
    assert len(application_policies) >= 4
    assert all(table_id in json.dumps(policy) or bucket_id in json.dumps(policy) for policy in application_policies)


def test_grants_use_read_or_native_write_actions_per_handler(monkeypatch):
    template = stack_template(monkeypatch)
    functions = {
        resource["Properties"]["Handler"]: resource
        for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler")
        in {"items.create_item", "items.get_item", "objects.put_object", "objects.get_object"}
    }
    policies = resources(template, "AWS::IAM::Policy").values()

    def actions_for(handler):
        role_ref = functions[handler]["Properties"]["Role"]["Fn::GetAtt"][0]
        return {
            action
            for policy in policies
            if {"Ref": role_ref} in policy["Properties"]["Roles"]
            for statement in policy["Properties"]["PolicyDocument"]["Statement"]
            for action in (statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]])
        }

    assert "dynamodb:PutItem" in actions_for("items.create_item")
    assert "dynamodb:PutItem" not in actions_for("items.get_item")
    assert "s3:PutObject" in actions_for("objects.put_object")
    assert "s3:PutObject" not in actions_for("objects.get_object")


def test_s3_cleanup_provider_is_not_in_the_application_vpc(monkeypatch):
    template = stack_template(monkeypatch)
    cleanup_functions = [
        resource for resource in resources(template, "AWS::Lambda::Function").values()
        if resource["Properties"].get("Handler") == "index.handler"
    ]
    assert cleanup_functions
    assert all("VpcConfig" not in function["Properties"] for function in cleanup_functions)
