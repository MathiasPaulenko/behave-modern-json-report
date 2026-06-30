# Schema Documentation

## Schema Version

Current version: `1.0.0`

The schema follows [Semantic Versioning](https://semver.org/):

- **Major** — Breaking changes (removed fields, changed types, changed semantics).
- **Minor** — Additive, backward-compatible changes (new optional fields).
- **Patch** — Clarifications and errata that do not change structure.

## Root Object

```json
{
  "schemaVersion": "1.0.0",
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
| `metadata` | object | Arbitrary user-supplied metadata |

### Optional Fields

| Field | Type | Description |
| ---- | ---- | ----------- |
| `environment` | object | Runtime environment info |

## Execution

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `executionId` | string | yes | Unique execution identifier |
| `projectName` | string\|null | no | Project name |
| `startTime` | string\|null | no | ISO-8601 start timestamp |
| `endTime` | string\|null | no | ISO-8601 end timestamp |
| `duration` | number | yes | Duration in seconds |
| `status` | string | yes | `passed` \| `failed` \| `skipped` |
| `command` | string\|null | no | Command that triggered the execution |
| `workingDirectory` | string\|null | no | Working directory |

## Statistics

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
| `passRate` | number | Pass rate (0.0–1.0) |
| `duration` | number | Total duration in seconds |

## Environment

| Field | Type | Description |
| ---- | ---- | ----------- |
| `pythonVersion` | string\|null | Python runtime version |
| `behaveVersion` | string\|null | Behave version |
| `platform` | string\|null | Platform identifier |
| `os` | string\|null | Operating system name |
| `osVersion` | string\|null | OS release version |
| `hostname` | string\|null | Machine hostname |
| `ciProvider` | string\|null | CI provider (if detected) |
| `extra` | object | Additional environment data |

## Feature

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique feature ID |
| `name` | string | yes | Feature name |
| `description` | string\|null | no | Feature description |
| `tags` | array&lt;string&gt; | no | Tags |
| `filename` | string\|null | no | Source file |
| `line` | integer\|null | no | Source line |
| `status` | string | yes | `passed` \| `failed` \| `skipped` |
| `duration` | number | yes | Duration in seconds |
| `scenarios` | array | yes | List of scenarios |

## Scenario

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique scenario ID |
| `name` | string | yes | Scenario name |
| `featureId` | string | yes | Parent feature ID |
| `description` | string\|null | no | Scenario description |
| `tags` | array&lt;string&gt; | no | Tags |
| `examples` | array | no | Example rows (for outlines) |
| `location` | object | no | Source location |
| `status` | string | yes | Step status |
| `duration` | number | yes | Duration in seconds |
| `retry` | object\|null | no | Retry info (future-ready) |
| `steps` | array | yes | List of steps |

## Step

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `id` | string | yes | Unique step ID |
| `keyword` | string | yes | `Given` \| `When` \| `Then` \| `And` \| `But` |
| `text` | string | yes | Step text |
| `status` | string | yes | Step status |
| `duration` | number | yes | Duration in seconds |
| `location` | object | no | Source location |
| `error` | object | no | Structured error |
| `docString` | object | no | Doc string content |
| `dataTable` | object | no | Data table |
| `attachments` | array | no | Attachments |
| `logs` | array | no | Log entries |

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

## Location

| Field | Type | Required | Description |
| ---- | ---- | -------- | ----------- |
| `filename` | string | yes | Source filename |
| `line` | integer | yes | Line number |
| `column` | integer\|null | no | Column number |

## Status Values

| Status | Description |
| ---- | ---- |
| `passed` | Step/scenario executed successfully |
| `failed` | Step/scenario failed |
| `skipped` | Step/scenario was skipped |
| `undefined` | No matching step definition found |
| `pending` | Step definition exists but is not yet implemented |
