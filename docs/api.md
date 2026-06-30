# API Reference

## `behave_modern_json_report`

### Top-level exports

```python
from behave_modern_json_report import (
    SCHEMA_VERSION,
    serialize,
    validate_report,
    validate_dict,
    # models...
)
```

### `SCHEMA_VERSION`

The current schema version string (e.g. `"1.0.0"`).

### `serialize(report, *, options=None) -> str`

Serialize an `ExecutionReport` to a JSON string.

```python
from behave_modern_json_report import serialize, SerializerOptions

json_str = serialize(report, options=SerializerOptions(pretty=False))
```

### `validate_report(report) -> ValidationResult`

Serialize and validate a report model.

### `validate_dict(data) -> ValidationResult`

Validate a JSON-ready dictionary against the schema.

### `validate_json(text) -> ValidationResult`

Parse and validate a JSON string.

---

## `SerializerOptions`

```python
SerializerOptions(
    pretty=True,
    include_environment=True,
    include_attachments=True,
    embed_attachments=True,
    exclude_passed_scenarios=False,
    indent=2,
    sort_keys=False,
    ensure_ascii=False,
)
```

---

## `Serializer`

```python
Serializer(options).to_dict(report) -> dict
Serializer(options).to_json(report) -> str
```

---

## `Collector`

```python
from behave_modern_json_report.collector import Collector

collector = Collector(project_name="my-app", metadata={"branch": "main"})
collector.start_feature(behave_feature)
collector.start_scenario(behave_scenario)
collector.start_step(behave_step)
collector.end_step(behave_step)
collector.end_scenario(behave_scenario)
collector.end_feature(behave_feature)
report = collector.finalize()
```

### `collector.add_attachment(...)`

```python
collector.add_attachment(
    name="screenshot",
    mime_type="image/png",
    encoding="base64",
    content="iVBORw0KGgo=",
)
```

### `collector.add_log(level, message)`

```python
collector.add_log("INFO", "Something happened")
```

---

## `ModernJSONFormatter`

```python
from behave_modern_json_report.formatter import ModernJSONFormatter
```

Used as a Behave formatter:

```bash
behave --format behave_modern_json_report:ModernJSONFormatter --outfile report.json
```

Or programmatically:

```python
fmt = ModernJSONFormatter(
    stream=open("report.json", "w"),
    options=SerializerOptions(pretty=True),
    project_name="my-app",
    metadata={"branch": "main"},
)
```

---

## `CucumberJSONFormatter`

```python
from behave_modern_json_report.cucumber_formatter import CucumberJSONFormatter
```

Produces a Cucumber-compatible JSON report (de facto standard) for integration
with tools like cucumber-reporting, multiple-cucumber-html-reporter, ReportPortal,
and Jenkins plugins.

Used as a Behave formatter:

```bash
behave --format behave_modern_json_report:CucumberJSONFormatter --outfile cucumber.json
```

Or programmatically:

```python
fmt = CucumberJSONFormatter(
    stream=open("cucumber.json", "w"),
    options=CucumberSerializerOptions(pretty=True),
    project_name="my-app",
    metadata={"branch": "main"},
)
```

---

## `CucumberSerializerOptions`

```python
CucumberSerializerOptions(
    pretty=True,
    indent=2,
    sort_keys=False,
    ensure_ascii=False,
    embed_attachments=True,
    include_output=True,
    include_hooks=True,
    include_background=True,
    duration_in_nanos=True,
)
```

---

## `CucumberSerializer`

```python
CucumberSerializer(options).to_list(report) -> list[dict]
CucumberSerializer(options).to_json(report) -> str
```

Also available as a convenience function:

```python
from behave_modern_json_report import serialize_cucumber

json_str = serialize_cucumber(report, options=CucumberSerializerOptions(pretty=False))
```

---

## Models

All models are dataclasses defined in `models.py`:

- `ExecutionReport` — root object
- `Execution` — execution metadata
- `Statistics` — aggregate stats
- `Environment` — runtime environment
- `Feature` — Gherkin feature
- `Scenario` — scenario or outline example
- `Step` — step
- `Error` — structured error
- `Attachment` — attachment
- `DocString` — doc string
- `DataTable` / `DataTableRow` — data table
- `Location` — source location
- `StepLog` — log entry
- `Metadata` — arbitrary metadata container
- `Background` — Gherkin background
