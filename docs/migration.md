# Migration Guide

## From `behave --format json` to `behave-modern-json-report`

### Why migrate?

The built-in Behave JSON formatter produces a flat, HTML-oriented structure that is difficult to consume programmatically. `behave-modern-json-report` provides:

- A **schema-versioned**, stable JSON model
- **Structured errors** (type, message, traceback, location) instead of raw strings
- **Stable identifiers** for every entity
- **Attachments** and **logs** at the step level
- **Statistics** computed and included in the output
- **Environment** detection (Python, Behave, OS, CI)
- **Arbitrary metadata** support
- **No Behave dependency** in the serializer — the JSON model is portable

### Command line

Before:

```bash
behave --format json --outfile report.json
```

After:

```bash
behave --format behave_modern_json_report:ModernJSONFormatter --outfile report.json
```

### Key structural differences

| Concept | Old JSON | New JSON |
| ------- | -------- | -------- |
| Root | Array of features | Object with `execution`, `statistics`, `features` |
| Errors | Raw string in `error_message` | Structured `error` object with `type`, `message`, `traceback` |
| IDs | Absent | Every entity has a unique `id` |
| Schema version | Absent | `schemaVersion: "1.0.0"` |
| Statistics | Absent | Computed `statistics` block |
| Environment | Absent | `environment` block |
| Attachments | Absent | `attachments` array on steps |
| Metadata | Absent | `metadata` object at root |

### Programmatic usage

If you were parsing the old JSON in Python:

```python
import json
data = json.load(open("report.json"))
for feature in data:  # list of features
    for scenario in feature["elements"]:
        for step in scenario["steps"]:
            ...
```

With the new format:

```python
import json
data = json.load(open("report.json"))
for feature in data["features"]:
    for scenario in feature["scenarios"]:
        for step in scenario["steps"]:
            ...
```

### Validation

You can now validate reports:

```python
from behave_modern_json_report import validate_json

result = validate_json(open("report.json").read())
if not result:
    for error in result.errors:
        print(error)
```
