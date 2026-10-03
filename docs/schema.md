# Schema Documentation

## Schema Version

Current version: `1.2.0`

The schema follows [Semantic Versioning](https://semver.org/):

- **Major** — Breaking changes (removed fields, changed types, changed semantics).
- **Minor** — Additive, backward-compatible changes (new optional fields).
- **Patch** — Clarifications and errata that do not change structure.

The bundled JSON Schema lives at
`behave_modern_json_report/schemas/execution.schema.json` (Draft 2020-12).

## Root Object

```json
{
  "schemaVersion": "1.2.0",
  "execution": { ... },
  "statistics": { ... },
  "environment": { ... },
  "features": [ ... ],
  "metadata": { ... }
}
```

### Required Fields

| Field | Type | Description |
| ---- | ---- | ----------- |
| `schemaVersion` | string | SemVer version of the schema |
| `execution` | object | Execution-level metadata |
| `statistics` | object | Aggregate statistics |
| `features` | array | List of features |
| `metadata` | object | Arbitrary user-supplied metadata (flat key-value map) |

### Optional Fields

| Field | Type | Description |
| ---- | ---- | ----------- |
| `environment` | object | Runtime environment info (omitted with `include_environment=False`) |

## Execution

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `executionId` | string | yes | Unique execution identifier |
| `projectName` | string\|null | no | Project name |
| `startTime` | string\|null | no | ISO-8601 start timestamp |
| `endTime` | string\|null | no | ISO-8601 end timestamp |
| `duration` | number | yes | Duration in seconds |
| `status` | string | yes | See [Status Values](#status-values) |
| `command` | string\|null | no | Command that triggered the execution |
| `workingDirectory` | string\|null | no | Working directory |

## Statistics

Step-level counts (`passed`, `failed`, `skipped`, `undefined`, `pending`)
count **steps**, not scenarios.

| Field | Type | Description |
| ---- | ---- | ----------- |
| `features` | integer | Total features |
| `scenarios` | integer | Total scenarios |
| `steps` | integer | Total steps |
| `passed` | integer | Passed steps |
| `failed` | integer | Failed steps |
| `skipped` | integer | Skipped steps |
| `undefined` | integer | Undefined steps |
| `pending` | integer | Pending steps |
| `passRate` | number | `passed / (passed + failed)` steps (0.0–1.0) |
| `duration` | number | Total duration in seconds |
| `errorCount` | integer | Steps with a failure-like status |
| `totalAttachments` | integer | Attachments across all steps |
| `totalLogs` | integer | Log entries across all steps |
| `slowestStepDuration` | number | Duration of the slowest step |
| `avgScenarioDuration` | number | Mean scenario duration |
| `commonExceptionType` | string\|null | Most frequent error `type` |
| `byTag` | object | Per-tag counters: `count`, `duration`, and per-status counts |

## Environment

All fields may be `null` when the value cannot be detected.

| Field | Type | Description |
| ---- | ---- | ----------- |
| `pythonVersion` | string\|null | Python runtime version |
| `behaveVersion` | string\|null | Behave version |
| `platform` | string\|null | `sys.platform` |
| `os` | string\|null | Operating system name |
| `osVersion` | string\|null | OS release version |
| `hostname` | string\|null | Machine hostname |
| `ciProvider` | string\|null | Detected CI provider |
| `cwd` | string\|null | Working directory |
| `command` | string\|null | Command line (`shlex.join(sys.argv)`) |
| `user` | string\|null | Current user |
| `cpuCount` | integer\|null | Logical CPU count |
| `memoryMb` | integer\|null | Total memory in MB (requires `psutil`, `[env]` extra) |
| `gitBranch` | string\|null | Current git branch |
| `gitCommit` | string\|null | Current git commit (short) |
| `gitRemote` | string\|null | `origin` remote URL |
| `extra` | object | Additional environment data (`python_implementation`, `machine`, `processor`, plus `environment_extra` metadata) |

## Feature

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique feature ID |
| `name` | string | yes | Feature name |
| `description` | string\|null | no | Feature description |
| `tags` | array&lt;string&gt; | no | Tags |
| `filename` | string\|null | no | Source file |
| `line` | integer\|null | no | Source line |
| `status` | string | yes | See [Status Values](#status-values) |
| `duration` | number | yes | Duration in seconds |
| `scenarios` | array | yes | All scenarios of the feature (flat list) |
| `rules` | array | no | Gherkin v6 rules with nested scenarios |
| `background` | object | no | Feature-level background |

> **Note on duplication:** scenarios that belong to a `Rule` appear **both**
> in the flat `scenarios` array and nested inside `rules[].scenarios`. The
> flat array is the canonical ordering; `rules` is a hierarchical view.
> Statistics count each scenario once.

## Rule

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique rule ID |
| `name` | string | yes | Rule name |
| `featureId` | string | yes | Parent feature ID |
| `description` | string\|null | no | Rule description |
| `tags` | array&lt;string&gt; | no | Tags |
| `location` | object | no | Source location |
| `background` | object | no | Rule-level background |
| `scenarios` | array | yes | Scenarios inside the rule |
| `status` | string | yes | See [Status Values](#status-values) |
| `duration` | number | yes | Duration in seconds |

## Scenario

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique scenario ID |
| `name` | string | yes | Scenario name (outline rows keep the row annotation) |
| `featureId` | string | yes | Parent feature ID |
| `description` | string\|null | no | Scenario description |
| `tags` | array&lt;string&gt; | no | Tags |
| `examples` | array | no | Example rows for outlines (`rowId` plus cell values) |
| `location` | object | no | Source location |
| `status` | string | yes | See [Status Values](#status-values) |
| `duration` | number | yes | Duration in seconds |
| `rule` | string\|null | no | Name of the containing rule |
| `ruleId` | string\|null | no | ID of the containing rule |
| `isOutline` | boolean | no | `true` for scenario-outline example rows |
| `outlineName` | string\|null | no | Name of the parent scenario outline |
| `exampleTags` | array&lt;string&gt; | no | Tags defined on the `Examples`/`Example` block |
| `background` | object | no | Effective background (rule background wins over feature) |
| `retry` | object | no | Retry info (future-ready, currently unused) |
| `steps` | array | yes | Steps in execution order (background steps first) |

## Step

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique step ID |
| `keyword` | string | yes | `Given` \| `When` \| `Then` \| `And` \| `But` |
| `text` | string | yes | Step text |
| `status` | string | yes | See [Status Values](#status-values) |
| `duration` | number | yes | Duration in seconds |
| `location` | object | no | Source location |
| `error` | object | no | Structured error |
| `docString` | object | no | Doc string content |
| `dataTable` | object | no | Data table |
| `attachments` | array | no | Attachments |
| `logs` | array | no | Log entries |

## Background

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique background ID |
| `name` | string | no | Background name |
| `keyword` | string | no | Usually `Background` |
| `location` | object | no | Source location |
| `steps` | array | no | Step definitions; statuses reflect the last executed scenario run |

## Error

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique error ID |
| `type` | string | yes | Exception type name |
| `message` | string | yes | Error message |
| `traceback` | string\|null | no | Full traceback |
| `location` | object | no | Source location |

## Attachment

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique attachment ID |
| `name` | string | yes | Display name |
| `mimeType` | string | yes | MIME type |
| `encoding` | string | yes | `raw` \| `base64` \| `external` |
| `content` | string\|null | no | Embedded content |
| `path` | string\|null | no | External file path |
| `url` | string\|null | no | External URL |
| `size` | integer\|null | no | Size in bytes |
| `timestamp` | string\|null | no | ISO-8601 timestamp |

## DocString

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `content` | string | yes | Doc string content |
| `contentType` | string\|null | no | Media type hint |
| `line` | integer\|null | no | Source line |

## DataTable / DataTableRow

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `headers` | array&lt;string&gt;\|null | no | Column headings |
| `rows` | array | yes | Rows (`cells` + optional `line`) |

## StepLog

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `timestamp` | string | yes | ISO-8601 timestamp |
| `level` | string | yes | Log level |
| `message` | string | yes | Log message |

## Location

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `filename` | string | yes | Source filename |
| `line` | integer | yes | Line number |
| `column` | integer\|null | no | Column number |

## Status Values

| Status | Description |
| ---- | ---- |
| `passed` | Executed successfully |
| `failed` | Failed |
| `skipped` | Skipped (not executed) |
| `undefined` | No matching step definition found (steps only) |
| `pending` | Step definition exists but is not yet implemented (steps only) |
| `untested` | Not executed (dry runs, steps without a result yet) |
| `error` | Errored (Behave marks scenarios with undefined/pending steps as `error`) |
| `hook_error` | A lifecycle hook failed |
| `cleanup_error` | Context cleanup after a scenario failed |
| `xfailed` | Expected failure — counted as a successful outcome |
| `xpassed` | Unexpected pass on a test marked as expected failure |
