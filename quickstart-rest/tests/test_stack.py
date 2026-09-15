import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest


def _docker_unavailable_reason():
    if shutil.which("docker") is None:
        return "Docker is required to bundle the Lambda function, but it is not installed"

    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "docker info failed"
        return f"Docker is required to bundle the Lambda function, but is unavailable: {detail}"

    return None


def test_stack_contains_rest_api_get_method_and_python_lambda():
    pytest.importorskip("aws_cdk", reason="aws-cdk-lib is required for the infrastructure test")
    pytest.importorskip(
        "lambda_api_decorators_cdk",
        reason="lambda-api-decorators-cdk is required for the infrastructure test",
    )

    docker_reason = _docker_unavailable_reason()
    if docker_reason:
        pytest.skip(docker_reason)

    import aws_cdk as cdk
    from aws_cdk.assertions import Template

    stack_source = (
        Path(__file__).parents[1] / "quickstart_rest" / "quickstart_rest_stack.py"
    )
    spec = importlib.util.spec_from_file_location("quickstart_rest_stack", stack_source)
    stack_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stack_module)

    app = cdk.App()
    stack = stack_module.QuickstartRestStack(app, "TestQuickstartRestStack")
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::Lambda::Function", 1)
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {"HttpMethod": "GET"},
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Resource",
        {"PathPart": "hello"},
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Runtime": "python3.14"},
    )
