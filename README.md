# Lambda API Decorators examples

This repository contains small, independent examples for building AWS Lambda APIs
with `lambda-api-decorators` and `lambda-api-decorators-cdk`. Each directory has
its own dependencies and setup instructions.

## Project links

- [Project site](https://infrastructure-as-decorator.github.io/)
- [Core package](https://github.com/infrastructure-as-decorator/lambda-api-decorators)
- [CDK integration](https://github.com/infrastructure-as-decorator/lambda-api-decorators-cdk)
- [Examples repository](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples)
- [Issues](https://github.com/infrastructure-as-decorator/lambda-api-decorators-examples/issues)

## Examples

- [`quickstart-rest`](quickstart-rest/) — create a minimal REST API with one
  `GET /hello` route.
- [`http-api`](http-api/) — create a minimal API Gateway HTTP API with one
  `GET /hello` route. It uses the HTTP API resource model, while
  `quickstart-rest` uses the REST API resource model.
