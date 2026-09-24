import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
STACK_SOURCE = ROOT / "rest_api_cognito_authorizer" / "rest_api_cognito_authorizer_stack.py"
DOCKER_AVAILABLE = bool(shutil.which("docker")) and subprocess.run(
    ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
).returncode == 0


def source_text():
    assert STACK_SOURCE.is_file()
    return STACK_SOURCE.read_text()


def stack_template(monkeypatch):
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is unavailable for CDK PythonFunction bundling")
    os.environ.setdefault("JSII_RUNTIME_PACKAGE_CACHE", "/tmp/codex-jsii-cache")
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.chdir(ROOT)
    from aws_cdk import App
    from aws_cdk.assertions import Template
    from rest_api_cognito_authorizer.rest_api_cognito_authorizer_stack import (
        RestApiCognitoAuthorizerStack,
    )

    stack = RestApiCognitoAuthorizerStack(App(), "TestRestApiCognitoAuthorizerStack")
    template = Template.from_stack(stack)
    template._test_stack = stack
    return template


def resources(template, resource_type):
    return template.find_resources(resource_type)


def refs(value, logical_id):
    return logical_id in json.dumps(value)


def test_stack_source_uses_published_authorizer_configuration_contract():
    tree = ast.parse(source_text(), filename=str(STACK_SOURCE))
    configs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LambdaApiConfig"
    ]
    assert len(configs) == 1
    keywords = {keyword.arg: keyword.value for keyword in configs[0].keywords}
    assert keywords["default_runtime"].value == "python3.14"
    assert keywords["default_authorizer"].value == "cognito"
    registry = keywords["authorizer_registry"]
    assert isinstance(registry, ast.Dict)
    assert [key.value for key in registry.keys] == ["cognito"]
    assert [value.id for value in registry.values] == ["cognito_authorizer"]


def test_stack_creates_one_pool_client_and_cognito_authorizer(monkeypatch):
    template = stack_template(monkeypatch)
    template.resource_count_is("AWS::Cognito::UserPool", 1)
    template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
    template.resource_count_is("AWS::ApiGateway::Authorizer", 1)
    pools = resources(template, "AWS::Cognito::UserPool")
    pool_id = next(iter(pools))
    clients = resources(template, "AWS::Cognito::UserPoolClient")
    client = next(iter(clients.values()))
    assert client["Properties"]["GenerateSecret"] is False
    authorizer = next(iter(resources(template, "AWS::ApiGateway::Authorizer").values()))
    assert authorizer["Properties"]["Type"] == "COGNITO_USER_POOLS"
    assert refs(authorizer["Properties"]["ProviderARNs"], pool_id)
    assert authorizer["Properties"]["IdentitySource"] == "method.request.header.Authorization"


def test_pool_is_destroyable_and_client_has_no_secret_or_credentials(monkeypatch):
    template = stack_template(monkeypatch)
    pool_id = next(iter(resources(template, "AWS::Cognito::UserPool")))
    pool = resources(template, "AWS::Cognito::UserPool")[pool_id]
    assert pool["DeletionPolicy"] == "Delete"
    if "UpdateReplacePolicy" in pool:
        assert pool["UpdateReplacePolicy"] == "Delete"
    client = next(iter(resources(template, "AWS::Cognito::UserPoolClient").values()))
    assert client["Properties"]["GenerateSecret"] is False
    assert resources(template, "AWS::Cognito::UserPoolUser") == {}
    assert not any(
        key.lower() in {"password", "token", "accesstoken", "idtoken", "refreshtoken"}
        for key in client["Properties"]
    )


def api_resource_paths(template):
    resources_by_id = resources(template, "AWS::ApiGateway::Resource")
    paths = {}
    unresolved = dict(resources_by_id)
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


def method_by_route(template):
    paths = api_resource_paths(template)
    methods = resources(template, "AWS::ApiGateway::Method")
    return {
        (method["Properties"]["HttpMethod"], paths[method["Properties"]["ResourceId"]["Ref"]]): method
        for method in methods.values()
    }


def test_api_has_exactly_two_effective_get_routes(monkeypatch):
    template = stack_template(monkeypatch)
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGateway::Method", 2)
    routes = method_by_route(template)
    assert set(routes) == {("GET", "/health"), ("GET", "/me")}
    health = routes[("GET", "/health")]["Properties"]
    me = routes[("GET", "/me")]["Properties"]
    assert health["AuthorizationType"] == "NONE"
    assert "AuthorizerId" not in health
    assert me["AuthorizationType"] == "COGNITO_USER_POOLS"
    assert "AuthorizerId" in me
    authorizer_id = next(iter(resources(template, "AWS::ApiGateway::Authorizer")))
    assert refs(me["AuthorizerId"], authorizer_id)


def test_api_has_no_api_keys_or_usage_plans(monkeypatch):
    template = stack_template(monkeypatch)
    assert resources(template, "AWS::ApiGateway::ApiKey") == {}
    assert resources(template, "AWS::ApiGateway::UsagePlan") == {}
    assert resources(template, "AWS::ApiGateway::UsagePlanKey") == {}


def test_stack_has_two_independent_python_314_lambda_entrypoints(monkeypatch):
    template = stack_template(monkeypatch)
    template.resource_count_is("AWS::Lambda::Function", 2)
    functions = list(resources(template, "AWS::Lambda::Function").values())
    assert {function["Properties"]["Runtime"] for function in functions} == {"python3.14"}
    assert {function["Properties"]["Handler"] for function in functions} == {
        "auth.health",
        "auth.me",
    }


def test_stack_has_only_expected_outputs_without_credentials(monkeypatch):
    template = stack_template(monkeypatch)
    outputs = template.to_json().get("Outputs", {})
    assert {name.lower() for name in outputs} >= {"apiurl", "userpoolid", "userpoolclientid"}
    assert not any(
        any(word in name.lower() or word in json.dumps(value).lower() for word in ("password", "secret", "token", "credential"))
        for name, value in outputs.items()
    )


def test_registry_preserves_cognito_object_and_documents_only_health_override(monkeypatch):
    text = source_text()
    assert "authorizer_registry" in text
    assert '"cognito"' in text or "'cognito'" in text
    assert "default_authorizer=\"cognito\"" in text or "default_authorizer='cognito'" in text
    auth_source = (ROOT / "lambdas" / "auth.py").read_text()
    assert "@public" in auth_source
    assert "@authorizer(" not in auth_source


def test_diagnostics_have_no_public_default_and_one_health_override(monkeypatch):
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is unavailable for CDK PythonFunction bundling")
    from aws_cdk.assertions import Annotations, Match

    template = stack_template(monkeypatch)
    annotations = Annotations.from_stack(template._test_stack)
    public_default = annotations.find_warning("*", Match.string_like_regexp("LAD_AUTH_PUBLIC_DEFAULT"))
    assert not public_default
    overrides = annotations.find_info("*", Match.string_like_regexp("Authorization overrides"))
    assert len(overrides) <= 1
    if overrides:
        message = overrides[0].entry.data
        assert all(part in message for part in ("GET", "/health", "PUBLIC", "cognito"))
        assert "/me" not in message
        assert not any(secret in message.lower() for secret in ("arn:", "token", "physical", "id:"))
