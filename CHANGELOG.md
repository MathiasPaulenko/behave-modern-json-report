# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-01-15

### Added

- **Background model**: Gherkin background steps are now captured at feature and scenario level.
- **Rule support**: Gherkin v6 / Behave 1.3.x rules are now tracked via `scenario.rule`.
- **Expanded statuses**: `untested`, `error`, `hook_error`, `cleanup_error`, `xfailed`, `xpassed` added to the canonical status vocabulary.
- **`normalize_status`** utility for safe enum/string status normalization.
- **Scenario outline fields**: `isOutline` and `outlineName` on scenarios.
- **Richer environment**: `cwd`, `command`, `user`, `cpuCount`, `memoryMb`, `gitBranch`, `gitCommit`, `gitRemote`.
- **Richer statistics**: `errorCount`, `totalAttachments`, `totalLogs`, `slowestStepDuration`, `avgScenarioDuration`, `commonExceptionType`, `byTag`.
- **Attachment helpers** (`attach.py`): `attach_file`, `attach_text`, `attach_json`, `attach_screenshot`, `log` for use in `environment.py` hooks.
- **Utility functions**: `format_duration`, `guess_mime`.
- **Metadata via `behave.userdata`**: all `mjr.*` keys from `[behave.userdata]` in `behave.ini` or `--userdata` CLI flag are automatically injected into the report's `metadata` block. `mjr.project_name` sets the project name.
- **Example Behave project** (`examples/behave_project/`): real multi-feature project with backgrounds, outlines, rules, tags, attachments, logging, and `mjr.*` metadata.
- **Release workflow** (`release.yml`): automatic PyPI publishing via Trusted Publishing on version bump.
- **Project hygiene**: `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `Makefile`.
- Optional `psutil` dependency for memory detection (`[env]` extra).

### Changed

- Schema `status` enums expanded to include all Behave statuses.
- JSON Schema updated with new `background`, `rule`, `isOutline`, `outlineName` definitions and extended `statistics`/`environment` properties.
- `Environment` and `Statistics` dataclasses expanded with new optional fields.
- `Collector` now captures background steps, rule names, and scenario outline metadata.
- `feature_status` and `scenario_status` now consider all failure-like statuses (`error`, `hook_error`, `cleanup_error`, `xfailed`).
- `ModernJSONFormatter` now inherits from Behave's `Formatter` base class and correctly handles multi-feature runs (`eof()` per file, `close()` at end).
- Python 3.14 added to CI test matrix and classifiers.

## [1.0.0] - 2026-06-30

### Added

- Initial stable release of `behave-modern-json-report`.
- Canonical JSON execution model for Behave with schema version `1.0.0`.
- Behave `Formatter` plugin that collects runtime events and serializes them.
- Pure-Python serializer with zero Behave dependency (model-driven).
- JSON Schema (`schemas/execution.schema.json`) for offline and runtime validation.
- Runtime validator with helpful, human-readable error messages.
- Structured error objects (type, message, traceback, location) instead of raw strings.
- Attachment support for image, json, xml, html, pdf, video, text and binary payloads.
- Embedded and external attachment references.
- Execution, feature, scenario and step level statistics.
- Environment detection (Python, Behave, platform, OS, hostname, CI provider).
- Stable unique identifiers for execution, features, scenarios, steps, attachments and errors.
- Configuration: pretty/compact JSON, embed/exclude attachments, exclude passed scenarios, custom metadata.
- `pyproject.toml` packaging ready for PyPI.
- MIT license.
- Unit, schema-validation, serialization, regression and golden-JSON test suites.
- GitHub Actions CI workflow (lint, type-check, tests, schema validation, coverage, packaging).

### Schema

- `schemaVersion: "1.0.0"` — the canonical, stable, backward-compatible schema.
