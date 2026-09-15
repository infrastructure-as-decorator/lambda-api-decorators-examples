import importlib.util
import json
from pathlib import Path


def test_hello_returns_an_api_gateway_proxy_response():
    source = Path(__file__).parents[1] / "lambdas" / "hello.py"
    spec = importlib.util.spec_from_file_location("hello", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    response = module.lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"message": "Hello, world!"}
    assert response == {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message": "Hello, world!"}',
    }
