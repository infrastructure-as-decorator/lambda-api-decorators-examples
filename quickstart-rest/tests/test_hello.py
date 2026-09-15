import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def test_hello_returns_an_api_gateway_proxy_response():
    source = Path(__file__).parents[1] / "lambdas" / "hello.py"
    decorators = ModuleType("lambda_api_decorators")
    decorators.get = lambda _path: lambda handler: handler
    sys.modules[decorators.__name__] = decorators
    spec = importlib.util.spec_from_file_location("hello", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    response = module.hello({}, None)

    assert response == {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"message": "Hello, world!"}',
    }
