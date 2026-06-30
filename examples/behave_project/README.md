# Example Behave Project

A real Behave project to test the `behave-modern-json-report` formatter.

## Structure

```text
behave_project/
├── behave.ini              # Behave configuration + mjr.* userdata
├── run.py                  # Convenience runner script
└── features/
    ├── environment.py      # Hooks with attach/log demonstrations
    ├── calculator.feature  # Arithmetic scenarios + background + outline
    ├── auth.feature        # Authentication scenarios + rule
    ├── shopping_cart.feature # Cart scenarios + background
    └── steps/
        ├── calculator_steps.py
        ├── auth_steps.py
        └── shopping_cart_steps.py
```

## Running

From the project root:

```bash
cd examples/behave_project
python run.py
```

Or manually:

```bash
cd examples/behave_project
PYTHONPATH=../../ behave --format behave_modern_json_report:ModernJSONFormatter \
    --outfile report.json --no-color features
```

The JSON report is written to `report.json` in the current directory.

## Metadata via `behave.ini`

The `behave.ini` includes a `[behave.userdata]` section with `mjr.*` keys:

```ini
[behave.userdata]
mjr.project_name = Behave Modern JSON Report - Example
mjr.branch = main
mjr.team = qa
mjr.environment = staging
mjr.build_id = local-dev
```

All `mjr.*` keys are injected into the report's `metadata.data` block (prefix stripped). `mjr.project_name` is used as the project name.

You can also override via CLI:

```bash
behave --userdata "mjr.branch=hotfix,mjr.build_id=99" features
```

## What It Demonstrates

- **Background steps** — `calculator.feature` and `shopping_cart.feature` use Gherkin backgrounds
- **Scenario outlines** — `calculator.feature` includes a scenario outline with examples
- **Rules** — `auth.feature` uses a Gherkin rule
- **Tags** — `@smoke`, `@regression`, `@fast`, `@outline` tags across features
- **Attachments** — `environment.py` attaches JSON context and failure details via `attach_json` / `attach_text`
- **Logging** — `environment.py` logs scenario lifecycle events via `log()`
- **Metadata** — `behave.ini` demonstrates `mjr.*` userdata injection into report metadata
- **Multiple features** — 3 feature files with 15 scenarios and 70 steps
