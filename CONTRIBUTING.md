# Contributing to behave-modern-json-report

Thank you for your interest in contributing! This document covers the process
for reporting bugs, suggesting features, and submitting pull requests.

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) or `pip` + `venv`
- Git

## Setup

```bash
git clone https://github.com/MathiasPaulenko/behave-modern-json-report.git
cd behave-modern-json-report
pip install -e ".[dev]"
```

## Running Tests

```bash
# Full suite (warnings as errors is the default in pyproject.toml)
pytest

# Relax warnings for Python 3.14 pre-existing deprecations
pytest -W default

# With coverage
pytest --cov=behave_modern_json_report --cov-report=term-missing
```

## Code Style

- Follow **PEP 8** and **PEP 257**.
- Use **type hints** on all public APIs.
- Prefer `pathlib`, context managers, dataclasses, and `logging`.
- Keep functions small and focused (Single Responsibility).
- No bare `except`, wildcard imports, or mutable default arguments.
- Comments should explain **why**, not **what**.

### Linting and Type Checking

```bash
# Type check
mypy behave_modern_json_report

# Lint
ruff check behave_modern_json_report tests
```

## Pull Request Process

1. **Fork** the repository and create a branch from `main`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Write tests** for your changes. Every new feature or bug fix should
   include test coverage.

3. **Run the full test suite** and ensure all tests pass:

   ```bash
   pytest -W default
   ```

4. **Update documentation** if your change affects the public API, JSON schema,
   or output format. Update `CHANGELOG.md` under the `[Unreleased]` section.

5. **Squash or rebase** your commits to keep history clean. Use
   [Conventional Commits](https://www.conventionalcommits.org/):

   ```text
   feat: add support for Gherkin v6 Rule backgrounds
   fix: correct scenario outline keyword detection
   docs: update README with short format names
   test: add tests for example tags extraction
   refactor: simplify cucumber serializer rule emission
   ```

6. **Open a Pull Request** using the PR template. Link any related issues.

### Pull Request Checklist

- [ ] Tests pass (`pytest -W default`)
- [ ] New code has test coverage
- [ ] Type hints added to public APIs
- [ ] `CHANGELOG.md` updated
- [ ] Documentation updated if needed
- [ ] No breaking changes (or clearly documented)

## Reporting Bugs

Use the **Bug Report** issue template. Include:

- Python version and OS
- Behave version
- `behave-modern-json-report` version
- Minimal reproduction steps
- Expected vs actual output
- Error traceback (if any)

## Suggesting Features

Use the **Feature Request** issue template. Describe:

- The problem you're trying to solve
- The proposed solution
- Alternatives considered
- Whether this aligns with the project's scope (JSON reporting for Behave)

## JSON Schema Changes

The JSON output format is versioned via `schemaVersion`. Any change to the
output structure requires:

1. A schema version bump in `behave_modern_json_report/schema.py`
2. Updated `$defs` in `behave_modern_json_report/schemas/execution.schema.json`
3. Updated tests in `tests/test_validator.py`
4. A note in `CHANGELOG.md` under a new version heading

## License

By contributing, you agree that your contributions will be licensed under the
MIT License that covers the project.
