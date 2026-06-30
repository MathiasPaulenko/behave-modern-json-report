# Architecture

## Overview

```text
Behave Events
      ↓
  Collector          (depends on Behave)
      ↓
 Execution Model     (pure dataclasses, no Behave)
      ↓
  Serializer         (no Behave dependency)
      ↓
    JSON
```

## Design Principles

1. **Behave isolation** — Only `collector.py` and `formatter.py` import Behave. The model, serializer, validator and statistics modules are pure Python with zero Behave dependency.
2. **Model-first** — The execution model (`models.py`) is the canonical representation. JSON is a serialization of the model, not the source of truth.
3. **Stable identifiers** — Every entity (execution, feature, scenario, step, attachment, error) has a unique `id` that is stable within a report.
4. **Schema versioning** — The `schemaVersion` field follows SemVer. Breaking changes require a major version bump.
5. **Forward compatibility** — Optional fields default to `None`. Future extensions (retry, parallel, AI analysis) can be added without breaking existing consumers.

## Module Responsibilities

| Module | Responsibility | Behave dependency |
| --- | --- | --- |
| `models.py` | Dataclasses for the execution model | None |
| `schema.py` | Schema version constants | None |
| `utils.py` | IDs, timing, safe conversions | None |
| `statistics.py` | Aggregate statistics computation | None |
| `environment.py` | Runtime environment detection | None |
| `serializer.py` | Model → JSON dict/string | None |
| `validator.py` | JSON Schema + structural validation | None |
| `collector.py` | Behave events → model | Behave |
| `formatter.py` | Behave Formatter API entrypoint | Behave |

## Data Flow

1. Behave fires events (`feature`, `scenario`, `step`, `result`).
2. `ModernJSONFormatter` delegates to `Collector`.
3. `Collector` builds `Feature`, `Scenario`, `Step` model objects.
4. On `eof()`/`close()`, `Collector.finalize()` produces an `ExecutionReport`.
5. `Serializer` converts the report to a JSON-ready dict, then `json.dumps`.
6. `Validator` can validate the output against the JSON Schema.

## Extending the Model

To add a new field:

1. Add it as an optional field in the relevant dataclass in `models.py`.
2. Add it to the JSON Schema in `schemas/execution.schema.json`.
3. Add serialization logic in `serializer.py`.
4. Add a test in `tests/`.
5. If additive and backward-compatible, bump the schema minor version.
