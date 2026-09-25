# Agent guidance

- Use `lambda-api-decorators-development` when available and resolve the installed package contracts before changing an example.
- Consume only published `lambda-api-decorators` and `lambda-api-decorators-cdk` distributions; never add Git, path, editable, or local-wheel requirements.
- Prefer public helpers such as `current_user` and `CurrentUserError`; do not parse authorizer claims manually or invent absent features.
- Keep one HTTP route per handler and handlers independently invokable. Keep registries separate from grants.
- Run focused handler and infrastructure tests, `compileall`, and `cdk synth --quiet`; Docker is required for synth/bundling in CI.
