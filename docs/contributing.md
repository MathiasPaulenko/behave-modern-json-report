# Contributing

Thank you for your interest in contributing to `behave-modern-json-report`!

## Development setup

```bash
git clone https://github.com/MathiasPaulenko/behave-modern-json-report.git
cd behave-modern-json-report
python -m pip install -e ".[dev]"
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Linting and type checking

```bash
ruff check behave_modern_json_report tests
mypy behave_modern_json_report
```

## Schema changes

Schema changes must follow the stability policy:

1. **Additive changes** (new optional fields) → bump minor version in `schema.py` and `execution.schema.json`.
2. **Breaking changes** (removed fields, changed types) → bump major version and document in `CHANGELOG.md`.
3. Always update the JSON Schema in both locations:
   - `behave_modern_json_report/schemas/execution.schema.json` (packaged)
   - `schemas/execution.schema.json` (repo-level copy)
4. Add tests for any new schema fields.

## Pull request checklist

- [ ] Tests pass (`pytest tests/`)
- [ ] Linting passes (`ruff check`)
- [ ] Schema updated (if structural changes)
- [ ] `CHANGELOG.md` updated
- [ ] Documentation updated (if user-facing changes)

## Release process

1. Update `version` in `pyproject.toml`.
2. Update `SCHEMA_VERSION` in `schema.py` if the schema changed.
3. Update `CHANGELOG.md`.
4. Tag the release: `git tag v1.0.x`.
5. Build: `python -m build`.
6. Publish to PyPI: `twine upload dist/*`.
