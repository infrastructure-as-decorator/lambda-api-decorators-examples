import ast
import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
LAMBDA_SOURCE = ROOT / "lambdas" / "auth.py"


def parse_source():
    return ast.parse(LAMBDA_SOURCE.read_text(), filename=str(LAMBDA_SOURCE))


def function_nodes():
    return {
        node.name: node
        for node in parse_source().body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def decorator_name(node):
    target = node.func if isinstance(node, ast.Call) else node
    return target.id if isinstance(target, ast.Name) else None


def route_decorators(function):
    return [
        decorator
        for decorator in function.decorator_list
        if isinstance(decorator, ast.Call)
        and decorator_name(decorator) in {"GET", "POST", "PUT", "DELETE", "ANY"}
    ]


def handler_module(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    sys.modules.pop("lambdas.auth", None)
    return importlib.import_module("lambdas.auth")


def invoke(module, name, event):
    result = getattr(module, name)(event, None)
    assert set(result) == {"statusCode", "headers", "body"}
    assert result["headers"] == {"Content-Type": "application/json"}
    assert isinstance(result["statusCode"], int)
    assert isinstance(result["body"], str)
    return result


def payload(result):
    return json.loads(result["body"])


def test_auth_module_contains_exactly_health_and_me_handlers():
    assert LAMBDA_SOURCE.is_file()
    assert set(function_nodes()) == {"health", "me"}


def test_handlers_have_one_route_and_expected_entrypoints():
    functions = function_nodes()
    expected = {"health": ("GET", "/health"), "me": ("GET", "/me")}
    for name, (method, path) in expected.items():
        routes = route_decorators(functions[name])
        assert len(routes) == 1
        assert decorator_name(routes[0]) == method
        assert len(routes[0].args) == 1
        assert routes[0].args[0].value == path


def test_health_is_explicitly_public_and_me_inherits_without_authorizer_override():
    functions = function_nodes()
    health_decorators = {decorator_name(node) for node in functions["health"].decorator_list}
    me_decorators = {decorator_name(node) for node in functions["me"].decorator_list}
    assert "public" in health_decorators
    assert "authorizer" not in me_decorators


def test_health_returns_a_valid_public_json_proxy_response(monkeypatch):
    module = handler_module(monkeypatch)
    result = invoke(module, "health", {})
    assert result["statusCode"] == 200
    assert payload(result) == {"status": "ok"}


def test_health_does_not_require_request_context(monkeypatch):
    module = handler_module(monkeypatch)
    assert payload(invoke(module, "health", {"resource": "/health"})) == {"status": "ok"}


def test_me_returns_only_required_identifiers_from_rest_claims(monkeypatch):
    module = handler_module(monkeypatch)
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-id",
                    "cognito:username": "alice",
                    "email": "alice@example.com",
                    "scope": "openid",
                }
            }
        }
    }
    result = invoke(module, "me", event)
    assert result["statusCode"] == 200
    assert payload(result) == {"sub": "user-id", "username": "alice"}


def test_me_uses_cognito_username_as_username(monkeypatch):
    module = handler_module(monkeypatch)
    event = {"requestContext": {"authorizer": {"claims": {"sub": "s", "cognito:username": "alice"}}}}
    assert payload(invoke(module, "me", event))["username"] == "alice"


def test_me_accepts_missing_cognito_username_when_sub_exists(monkeypatch):
    module = handler_module(monkeypatch)
    event = {"requestContext": {"authorizer": {"claims": {"sub": "user-id"}}}}
    result = invoke(module, "me", event)
    assert result["statusCode"] == 200
    assert payload(result) == {"sub": "user-id"}


def test_me_returns_defensive_401_when_claims_are_missing(monkeypatch):
    module = handler_module(monkeypatch)
    result = invoke(module, "me", {})
    assert result["statusCode"] == 401
    assert payload(result) == {"message": "Unauthorized"}


def test_me_does_not_return_tokens_authorization_header_or_all_claims(monkeypatch):
    module = handler_module(monkeypatch)
    claims = {
        "sub": "s",
        "cognito:username": "alice",
        "access_token": "access-secret",
        "id_token": "id-secret",
        "refresh_token": "refresh-secret",
        "Authorization": "Bearer secret",
        "email": "alice@example.com",
    }
    result = invoke(module, "me", {"requestContext": {"authorizer": {"claims": claims}}})
    body = result["body"]
    assert result["statusCode"] == 200
    assert payload(result) == {"sub": "s", "username": "alice"}
    assert all(secret not in body for secret in ("access-secret", "id-secret", "refresh-secret", "Bearer secret"))


def test_handlers_do_not_import_or_call_aws_services():
    tree = parse_source()
    forbidden = {"boto3", "botocore", "aws_sdk"}
    assert not any(
        isinstance(node, ast.Import) and any(alias.name.split(".")[0] in forbidden for alias in node.names)
        or isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in forbidden
        for node in tree.body
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"client", "resource", "get_user", "admin_get_user"}
        for node in ast.walk(tree)
    )

