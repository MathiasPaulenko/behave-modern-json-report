# behave-modern-json-report

A modern JSON report formatter for [Behave](https://github.com/behave/behave)
that generates a rich, structured execution model for reporting, analytics,
dashboards, AI, CI/CD pipelines and custom integrations.

## Quick Start

```bash
pip install behave-modern-json-report[behave]

behave --format modern-json --outfile report.json
```

```bash
# Cucumber-compatible JSON
behave --format cucumber-json --outfile cucumber.json
```

## Contents

- [Schema Documentation](schema.md) — field-by-field reference of the JSON output
- [Architecture](architecture.md) — how the pieces fit together
- [API Reference](api.md) — serializers, validators, collectors, formatters
- [Migration Guide](migration.md) — moving from `behave --format json`
- [Contributing](contributing.md) — development setup and workflow

See the [README](https://github.com/MathiasPaulenko/behave-modern-json-report/blob/main/README.md)
for the full feature list, configuration options and metadata support.
