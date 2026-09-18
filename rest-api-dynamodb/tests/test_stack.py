import json
import sys
from pathlib import Path

import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

sys.path.insert(0, str(Path(__file__).parents[1]))

from rest_api_dynamodb.rest_api_dynamodb_stack import RestApiDynamodbStack


def template(monkeypatch):
    monkeypatch.chdir(Path(__file__).parents[1])
    app = cdk.App()
    return Template.from_stack(RestApiDynamodbStack(app, "TestRestApiDynamodbStack"))


def test_stack_creates_real_rest_api_table_and_five_lambdas(monkeypatch):
    rendered = template(monkeypatch)
    rendered.resource_count_is("AWS::ApiGateway::RestApi", 1)
    rendered.resource_count_is("AWS::DynamoDB::Table", 1)
    rendered.resource_count_is("AWS::Lambda::Function", 5)
    rendered.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "Orders",
            "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        },
    )
    rendered.has_resource(
        "AWS::DynamoDB::Table",
        {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"},
    )
    methods = rendered.find_resources("AWS::ApiGateway::Method")
    assert {method["Properties"]["HttpMethod"] for method in methods.values()} == {
        "GET", "POST", "PUT", "DELETE"
    }
    assert len(methods) == 5


def test_lambda_defaults_and_configured_decorator_are_synthesized(monkeypatch):
    rendered = template(monkeypatch)
    functions = rendered.find_resources("AWS::Lambda::Function")
    defaults = [resource for resource in functions.values() if resource["Properties"].get("Runtime") == "python3.14"]
    assert len(defaults) == 4
    configured = [resource for resource in functions.values() if resource["Properties"].get("FunctionName") == "configured-handler"]
    assert len(configured) == 1
    properties = configured[0]["Properties"]
    assert properties["Runtime"] == "python3.12"
    assert properties["MemorySize"] == 1024
    assert properties["Timeout"] == 15
    assert properties["Description"] == "Configured endpoint"
    assert properties["Environment"]["Variables"]["STAGE"] == "dev"
    assert "Orders" in json.dumps(properties["Environment"]["Variables"]["TABLE_NAME"])
    assert properties["Role"]["Fn::GetAtt"][1] == "Arn"
    assert properties["Role"]["Fn::GetAtt"][0].startswith("ApiRole")
    roles = rendered.find_resources("AWS::IAM::Role")
    assert any(
        role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]
        == {"Service": "lambda.amazonaws.com"}
        and any("AWSLambdaBasicExecutionRole" in json.dumps(policy)
                for policy in role["Properties"]["ManagedPolicyArns"])
        for role in roles.values()
    )


def test_dynamodb_permissions_are_scoped_and_read_write_is_cumulative(monkeypatch):
    rendered = template(monkeypatch)
    policies = rendered.find_resources("AWS::IAM::Policy")
    statements = [
        statement
        for policy in policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
        if any("dynamodb:" in action for action in statement["Action"] if isinstance(statement["Action"], list))
    ]
    assert statements
    assert all(statement["Resource"] != "*" for statement in statements)
    actions = [set(statement["Action"]) for statement in statements]
    assert any("dynamodb:Scan" in action_set for action_set in actions)
    assert any({"dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"}.issubset(action_set) for action_set in actions)
