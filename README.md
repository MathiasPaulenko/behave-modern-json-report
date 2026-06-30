# behave-modern-json-report

A modern JSON report formatter for [Behave](https://github.com/behave/behave) that generates a rich, structured execution model for reporting, analytics, dashboards, AI, CI/CD pipelines and custom integrations.

[![CI](https://github.com/MathiasPaulenko/behave-modern-json-report/actions/workflows/ci.yml/badge.svg)](https://github.com/MathiasPaulenko/behave-modern-json-report/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Schema Version](https://img.shields.io/badge/schema-1.1.0-green.svg)](docs/schema.md)

---

## Why?

The built-in Behave JSON formatter produces a flat, HTML-oriented structure. This project creates the **canonical execution model** for Behave — a schema-versioned, stable, extensible JSON format designed as an API, not as a rendering target.

It is the data foundation for:

- HTML / Markdown / Console reports
- AI-powered test analysis
- Dashboards and analytics platforms
- Historical execution comparison
- Trace viewers
- Custom integrations

## Features

- **Schema-versioned** JSON output (`schemaVersion: "1.1.0"`)
- **Stable unique identifiers** for every entity (execution, feature, scenario, step, attachment, error)
- **Structured errors** — type, message, traceback, location (never raw strings)
- **Attachments** — image, JSON, XML, HTML, PDF, video, text, binary; embedded or external
- **Attachment helpers** — `attach_file`, `attach_text`, `attach_json`, `attach_screenshot`, `log` for `environment.py` hooks
- **Step-level logs**
- **Gherkin backgrounds** — shared background steps captured at feature and scenario level
- **Rule support** — Gherkin v6 / Behave 1.3.x rules tracked via `scenario.rule`
- **Scenario outlines** — `isOutline` and `outlineName` fields
- **Expanded statuses** — `passed`, `failed`, `skipped`, `undefined`, `pending`, `untested`, `error`, `hook_error`, `cleanup_error`, `xfailed`, `xpassed`
- **Rich statistics** — pass rate, counts, duration, error count, total attachments/logs, slowest step, avg scenario, common exception type, per-tag breakdown
- **Rich environment** — Python, Behave, platform, OS, hostname, CI provider, cwd, command, user, CPU count, memory, git branch/commit/remote
- **Arbitrary metadata** — inject domain-specific context via `[behave.userdata]` with `mjr.*` keys
- **Zero Behave dependency** in the serializer — the JSON model is portable
- **JSON Schema** validation with helpful error messages
- **Configurable** — pretty/compact, embed/exclude attachments, exclude passed scenarios
- **Production-ready** — 101 tests, lint, type-check, CI

## Installation

```bash
pip install behave-modern-json-report[behave]
```

For validation support:

```bash
pip install behave-modern-json-report[validate]
```

For enhanced environment detection (memory info):

```bash
pip install behave-modern-json-report[env]
```

For development:

```bash
pip install behave-modern-json-report[dev]
```

## Quick Start

### As a Behave formatter

```bash
behave --format behave_modern_json_report:ModernJSONFormatter --outfile report.json
```

### With metadata via `behave.ini`

```ini
[behave]
format = behave_modern_json_report:ModernJSONFormatter
outfile = report.json

[behave.userdata]
mjr.project_name = My Project
mjr.branch = dev
mjr.team = qa
mjr.environment = staging
mjr.build_id = 42
```

All keys prefixed with `mjr.` are automatically injected into the report's `metadata` block. `mjr.project_name` is used as the project name. The prefix is stripped in the output:

```json
{
  "execution": { "projectName": "My Project" },
  "metadata": { "data": { "branch": "dev", "team": "qa", "environment": "staging", "build_id": "42" } }
}
```

You can also pass metadata via CLI:

```bash
behave --userdata "mjr.branch=hotfix,mjr.build_id=99" --format behave_modern_json_report:ModernJSONFormatter --outfile report.json
```

### Programmatically

```python
from behave_modern_json_report import serialize, SerializerOptions
from behave_modern_json_report.collector import Collector

collector = Collector(project_name="my-app", metadata={"branch": "main"})

# Feed Behave events to the collector...
# collector.start_feature(feature)
# collector.start_scenario(scenario)
# collector.start_step(step)
# collector.end_step(step)
# collector.end_scenario(scenario)
# collector.end_feature(feature)

report = collector.finalize()
json_str = serialize(report, options=SerializerOptions(pretty=True))
```

### Validation

```python
from behave_modern_json_report import validate_json

result = validate_json(open("report.json").read())
if not result:
    for error in result.errors:
        print(f"{error.path}: {error.message}")
```

## JSON Structure

```json
{
  "schemaVersion": "1.0.0",
  "execution": {
    "executionId": "exec-...",
    "projectName": "my-app",
    "startTime": "2026-06-30T14:20:00.000Z",
    "endTime": "2026-06-30T14:20:01.500Z",
    "duration": 1.5,
    "status": "passed",
    "command": "behave ...",
    "workingDirectory": "/home/user/project"
  },
  "statistics": {
    "features": 1,
    "scenarios": 3,
    "steps": 12,
    "passed": 12,
    "failed": 0,
    "skipped": 0,
    "undefined": 0,
    "pending": 0,
    "passRate": 1.0,
    "duration": 1.5,
    "errorCount": 0,
    "totalAttachments": 0,
    "totalLogs": 0,
    "slowestStepDuration": 0.2,
    "avgScenarioDuration": 0.5
  },
  "environment": {
    "pythonVersion": "3.12.3",
    "behaveVersion": "1.2.6",
    "platform": "linux",
    "os": "Linux",
    "osVersion": "6.5.0",
    "hostname": "build-agent-01",
    "ciProvider": "github-actions",
    "cwd": "/home/user/project",
    "command": "behave --format json-modern",
    "user": "tester",
    "cpuCount": 8,
    "memoryMb": 16384,
    "gitBranch": "main",
    "gitCommit": "abc1234",
    "gitRemote": "origin"
  },
  "features": [
    {
      "id": "feature-...",
      "name": "Calculator",
      "tags": ["smoke"],
      "status": "passed",
      "duration": 1.5,
      "scenarios": [
        {
          "id": "scenario-...",
          "name": "Add two numbers",
          "featureId": "feature-...",
          "status": "passed",
          "duration": 0.5,
          "steps": [
            {
              "id": "step-...",
              "keyword": "Given",
              "text": "I have entered 5 into the calculator",
              "status": "passed",
              "duration": 0.1
            }
          ]
        }
      ]
    }
  ],
  "metadata": {
    "data": {
      "browser": "Chrome",
      "environment": "QA",
      "branch": "main"
    }
  }
}
```

See [examples/golden-report.json](examples/golden-report.json) for a complete example.

## Configuration

`SerializerOptions` controls the output:

```python
from behave_modern_json_report import SerializerOptions

opts = SerializerOptions(
    pretty=True,                    # Indented JSON
    include_environment=True,       # Include environment block
    include_attachments=True,       # Include attachment metadata
    embed_attachments=True,         # Embed attachment content inline
    exclude_passed_scenarios=False, # Drop passed scenarios (failure-only)
    indent=2,                       # Indentation level
    sort_keys=False,                # Sort keys lexicographically
    ensure_ascii=False,             # Escape non-ASCII characters
)
```

## Architecture

```text
Behave Events → Collector → Execution Model → Serializer → JSON
```

Only `collector.py` and `formatter.py` depend on Behave. The model, serializer, validator and statistics modules are pure Python.

See [docs/architecture.md](docs/architecture.md) for details.

## Documentation

- [Schema Documentation](docs/schema.md)
- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)
- [Migration Guide](docs/migration.md)
- [Contributing](docs/contributing.md)
- [Changelog](CHANGELOG.md)

## Project Structure

```text
behave-modern-json-report/
├── behave_modern_json_report/
│   ├── __init__.py
│   ├── formatter.py        # Behave Formatter API entrypoint
│   ├── collector.py        # Behave events → model (only Behave dep)
│   ├── serializer.py       # Model → JSON (no Behave dep)
│   ├── schema.py           # Schema version constants
│   ├── validator.py        # JSON Schema + runtime validation
│   ├── models.py           # Execution model dataclasses
│   ├── statistics.py       # Statistics aggregator
│   ├── environment.py      # Runtime environment detection
│   ├── attach.py           # High-level attachment helpers for hooks
│   ├── utils.py            # IDs, timing, status, MIME helpers
│   └── schemas/
│       └── execution.schema.json
├── examples/
│   ├── behave_project/       # Real behave project example
│   │   ├── behave.ini
│   │   ├── run.py
│   │   └── features/
│   ├── calculator.feature
│   └── golden-report.json
├── docs/
├── tests/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── pyproject.toml
├── Makefile
├── README.md
├── LICENSE
└── CHANGELOG.md
```

## Testing

```bash
python -m pytest tests/ -v
```

Test suites:

- **Unit tests** — utils, statistics, environment, attachments
- **Schema validation tests** — golden report, invalid reports
- **Serialization tests** — all model fields, options, backgrounds, rules
- **Regression tests** — collector lifecycle, formatter output
- **Golden JSON tests** — structural stability

## License

MIT — see [LICENSE](LICENSE).
