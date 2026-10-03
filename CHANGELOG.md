# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2026-10-03

### Fixed

- **Step results were never applied**: Behave emits all `step()` events before execution and `result()` events during it, so results were routed to the wrong step and then dropped. Every step reported `passed` with no error, even for failing or undefined steps. Results are now resolved by Behave step identity.
- **Skipped and undefined steps reported as `passed`**: steps that never produce a `result()` event (skipped after a failure, tag/hook-skipped) are now reconciled at scenario end from `scenario.all_steps` and keep their real status.
- **Scenario, feature and rule statuses** now prefer the Behave object's own status, so `error`, `hook_error` and `cleanup_error` propagate correctly. The derived fallback no longer collapses `undefined`/`pending`/`untested` into `passed` — it follows Behave semantics (`undefined`/`pending` steps mark the scenario `error`).
- **`isOutline`, `outlineName`, `examples` and `exampleTags`** were never populated in real runs: Behave builds example rows as plain `Scenario` objects. They are now detected via the `_row` attribute and the `ScenarioOutline` parent, including the example row values (`rowId` plus the row cells) and Example-block tags.
- **Background steps reported `untested` forever**: the background snapshot is now synced with the statuses the steps actually got inside each scenario.
- **`rule_finished()` hook added**: Behave calls it when a rule ends. `rule.duration` no longer absorbs scenarios from outside the rule.
- **Attachments and logs from hooks** (`before_scenario`, `after_step`, `after_scenario`, …) were silently dropped or bound to the wrong step. They are now buffered and bound to the step that is actually executing.
- **`CucumberJSONFormatter`** gained the `scenario_result` and `feature_result` aliases that `ModernJSONFormatter` already had.
- **Short format names were unusable**: Behave does not read `behave.formatters` entry points from installed packages, so `--format modern-json` failed. Short names must be registered in a `[behave.formatters]` section of `behave.ini`; the dead `entry-points` declaration was removed and the README now documents the working mechanism.
- **Structural validator**: required-field errors now include the field name in the message (the jsonschema path already did).
- **`Step.status` default** is now `untested` instead of `passed`.
- **`untested_undefined`** (Behave `--dry-run` status) now maps to `untested` instead of leaking a value outside the schema enum.
- **`__version__`** matched `pyproject.toml` again (`1.2.0`).

### Documentation

- `docs/schema.md` rewritten for schema `1.2.0` (rules, backgrounds, new statistics/environment fields, full status list).
- `README.md`, `docs/migration.md` and the example `README` showed `metadata` wrapped in a `data` object; the actual output is flat.
- `CONTRIBUTING.md` / `docs/contributing.md`: fixed the non-existent second schema path and the outdated manual release process (releases are automated via `release.yml`).
- `SECURITY.md` supported-versions table updated to `1.2.x`.
- `CHANGELOG.md` date for `1.1.0` corrected (it predated `1.0.0`).

## [1.2.0] - 2026-08-10

### Added

- **Gherkin v6 full support**:
  - **Rule dataclass**: first-class `Rule` entity with `id`, `name`, `description`, `tags`, `location`, `background`, `scenarios`, `status`, `duration`.
  - **Rule backgrounds**: backgrounds defined inside a `Rule` are captured and associated with the rule and its scenarios.
  - **Tags on Examples**: `exampleTags` field on scenarios captures tags specific to `Example` blocks.
  - **`Example` keyword**: Gherkin v6 `Example` keyword is now recognised as a scenario outline type.
  - **`ruleId` field**: scenarios inside a rule carry the rule's ID for hierarchical linking.
  - **`rules` array on features**: features now include a `rules` array with full rule entities in both modern JSON and Cucumber JSON output.
  - **`rule_status()`**: new statistics function to derive rule status from its scenarios.
  - **Entry points**: `modern-json` and `cucumber-json` short format names registered as `behave.formatters` entry points.
- **CucumberJSONFormatter**: new Behave formatter (`cucumber-json`) that outputs de facto Cucumber JSON report format for compatibility with cucumber-reporting, multiple-cucumber-html-reporter, ReportPortal, Jenkins plugins, and other tools that consume Cucumber JSON.
- **CucumberSerializer**: model-to-Cucumber JSON serializer with configurable options (pretty/compact, embed attachments, include output, include backgrounds, duration in nanos).
- **serialize_cucumber()**: convenience function for programmatic use.
- 24 new tests covering Gherkin v6 features (rules, backgrounds, example tags, Example keyword).
- 22 new tests covering Cucumber serializer and formatter.

### Fixed

- **`_FAILED_STATUSES` no longer includes `xfailed`**: `xfailed` means "expected failure" — the test was expected to fail and it did, which is a successful outcome. Including it in failed statuses caused incorrect overall status and error count inflation.
- **`CucumberJSONFormatter.add_attachment` / `add_log`**: these methods were missing, causing attachments and logs to silently fail when using the Cucumber formatter. Both methods now delegate to the collector, matching `ModernJSONFormatter`'s API.
- **`CucumberJSONFormatter._flush`**: now calls `flush()` on the stream and includes a file-path fallback when the stream object has no `write` method, matching `ModernJSONFormatter._flush`.
- **`exclude_passed_scenarios` now applies to rule scenarios**: previously, passed scenarios inside rules were not filtered when this option was enabled, creating inconsistency between top-level and rule-level scenario lists.
- **Structural validator now validates `rules` array**: when `jsonschema` is not installed, the fallback structural validator did not validate the `rules` array on features. Rules are now validated with the same thoroughness as features and scenarios.
- **Collector lifecycle**: `end_rule()` now finalizes any active scenario before ending the rule. `end_feature()` now finalizes any active scenario when no rule is active. This prevents dangling scenario state with unset status/duration.
- **`_overall_status` now checks all failed statuses**: previously only checked `STATUS_FAILED`, missing `error`, `hook_error`, and `cleanup_error` statuses. Now uses `_FAILED_STATUSES` frozenset for consistency.
- **`format_duration` type hint**: parameter type now correctly accepts `float | None` to match runtime behavior.
- **Dead code removal**: `CucumberSerializerOptions.include_hooks` was defined but never used in serialization logic — removed from options, formatter config parsing, and docs.
- **Inline imports moved to module top**: `import json` in `formatter.py`, `import os` in `cucumber_formatter.py`, and `import json` / `import io` in `attach.py` were inline in functions — moved to top-level imports.
- **Formatter `name` attribute mismatch**: `ModernJSONFormatter.name` was `"json-modern"` but the entry point in `pyproject.toml` registers it as `"modern-json"`. Fixed to match.

### Changed

- **License declaration modernized** (PEP 639): `license = { text = "MIT" }` replaced with `license = "MIT"` and deprecated `License ::` classifier removed from `pyproject.toml`.
- **`schemas` subpackage** explicitly declared in `pyproject.toml` to eliminate setuptools warning about ambiguous package configuration.

## [1.1.0] - 2026-07-20

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
