"""Serializer — converts the execution model into JSON-ready dictionaries.

The serializer has **no** dependency on Behave.  It operates exclusively on
the dataclasses defined in :mod:`behave_modern_json_report.models`.

Configuration is handled through :class:`SerializerOptions`.
"""

from __future__ import annotations

import json
from typing import Any

from .models import (
    Attachment,
    Background,
    DataTable,
    DocString,
    Environment,
    Error,
    Execution,
    ExecutionReport,
    Feature,
    Location,
    Metadata,
    Scenario,
    Statistics,
    Step,
    StepLog,
)
from .utils import STATUS_PASSED


class SerializerOptions:
    """Configuration for :class:`Serializer`.

    Attributes
    ----------
    pretty:
        When ``True`` emit indented JSON (2 spaces).  Otherwise compact.
    include_environment:
        Include the ``environment`` block in the output.
    include_attachments:
        Include attachment payloads.  When ``False`` attachments are omitted.
    embed_attachments:
        When ``True`` embed attachment content inline.  When ``False`` only
        external references (``path`` / ``url``) are kept.
    exclude_passed_scenarios:
        Drop scenarios whose status is ``passed``.  Useful for failure-only
        reports.  Features with no remaining scenarios are also dropped.
    indent:
        Indentation level when ``pretty`` is ``True``.
    sort_keys:
        Sort object keys lexicographically.
    ensure_ascii:
        Forwarded to :func:`json.dumps`.
    """

    __slots__ = (
        "pretty",
        "include_environment",
        "include_attachments",
        "embed_attachments",
        "exclude_passed_scenarios",
        "indent",
        "sort_keys",
        "ensure_ascii",
    )

    def __init__(
        self,
        *,
        pretty: bool = True,
        include_environment: bool = True,
        include_attachments: bool = True,
        embed_attachments: bool = True,
        exclude_passed_scenarios: bool = False,
        indent: int = 2,
        sort_keys: bool = False,
        ensure_ascii: bool = False,
    ) -> None:
        self.pretty = pretty
        self.include_environment = include_environment
        self.include_attachments = include_attachments
        self.embed_attachments = embed_attachments
        self.exclude_passed_scenarios = exclude_passed_scenarios
        self.indent = indent
        self.sort_keys = sort_keys
        self.ensure_ascii = ensure_ascii

    def to_json_kwargs(self) -> dict[str, Any]:
        """Return kwargs suitable for :func:`json.dumps`."""
        kwargs: dict[str, Any] = {
            "ensure_ascii": self.ensure_ascii,
            "sort_keys": self.sort_keys,
        }
        if self.pretty:
            kwargs["indent"] = self.indent
        else:
            kwargs["separators"] = (",", ":")
        return kwargs


# ---------------------------------------------------------------------------
# Field-name mapping (snake_case → camelCase is intentionally NOT applied;
# the canonical schema uses snake_case for stability and readability).
# ---------------------------------------------------------------------------


def _location_to_dict(loc: Location | None) -> dict[str, Any] | None:
    if loc is None:
        return None
    d: dict[str, Any] = {
        "filename": loc.filename,
        "line": loc.line,
    }
    if loc.column is not None:
        d["column"] = loc.column
    return d


def _doc_string_to_dict(ds: DocString | None) -> dict[str, Any] | None:
    if ds is None:
        return None
    d: dict[str, Any] = {"content": ds.content}
    if ds.content_type is not None:
        d["contentType"] = ds.content_type
    if ds.line is not None:
        d["line"] = ds.line
    return d


def _data_table_to_dict(dt: DataTable | None) -> dict[str, Any] | None:
    if dt is None:
        return None
    rows = []
    for row in dt.rows:
        r: dict[str, Any] = {"cells": list(row.cells)}
        if row.line is not None:
            r["line"] = row.line
        rows.append(r)
    d: dict[str, Any] = {"rows": rows}
    if dt.headers is not None:
        d["headers"] = list(dt.headers)
    return d


def _error_to_dict(err: Error | None) -> dict[str, Any] | None:
    if err is None:
        return None
    d: dict[str, Any] = {
        "id": err.id,
        "type": err.type,
        "message": err.message,
    }
    if err.traceback is not None:
        d["traceback"] = err.traceback
    if err.location is not None:
        d["location"] = _location_to_dict(err.location)
    return d


def _attachment_to_dict(att: Attachment, *, embed: bool) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": att.id,
        "name": att.name,
        "mimeType": att.mime_type,
        "encoding": att.encoding,
    }
    if embed and att.encoding != "external" and att.content is not None:
        d["content"] = att.content
    if att.path is not None:
        d["path"] = att.path
    if att.url is not None:
        d["url"] = att.url
    if att.size is not None:
        d["size"] = att.size
    if att.timestamp is not None:
        d["timestamp"] = att.timestamp
    return d


def _step_log_to_dict(log: StepLog) -> dict[str, Any]:
    return {
        "timestamp": log.timestamp,
        "level": log.level,
        "message": log.message,
    }


def _background_to_dict(
    bg: Background | None, *, options: SerializerOptions
) -> dict[str, Any] | None:
    if bg is None:
        return None
    d: dict[str, Any] = {
        "id": bg.id,
        "name": bg.name,
        "keyword": bg.keyword,
    }
    if bg.location is not None:
        d["location"] = _location_to_dict(bg.location)
    if bg.steps:
        d["steps"] = [_step_to_dict(s, options=options) for s in bg.steps]
    return d


def _step_to_dict(step: Step, *, options: SerializerOptions) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": step.id,
        "keyword": step.keyword,
        "text": step.text,
        "status": step.status,
        "duration": step.duration,
    }
    if step.location is not None:
        d["location"] = _location_to_dict(step.location)
    if step.error is not None:
        d["error"] = _error_to_dict(step.error)
    if step.doc_string is not None:
        d["docString"] = _doc_string_to_dict(step.doc_string)
    if step.data_table is not None:
        d["dataTable"] = _data_table_to_dict(step.data_table)
    if options.include_attachments and step.attachments:
        d["attachments"] = [
            _attachment_to_dict(a, embed=options.embed_attachments) for a in step.attachments
        ]
    if step.logs:
        d["logs"] = [_step_log_to_dict(entry) for entry in step.logs]
    return d


def _scenario_to_dict(scenario: Scenario, *, options: SerializerOptions) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": scenario.id,
        "name": scenario.name,
        "featureId": scenario.feature_id,
        "status": scenario.status,
        "duration": scenario.duration,
    }
    if scenario.description is not None:
        d["description"] = scenario.description
    if scenario.tags:
        d["tags"] = list(scenario.tags)
    if scenario.examples:
        d["examples"] = list(scenario.examples)
    if scenario.location is not None:
        d["location"] = _location_to_dict(scenario.location)
    if scenario.rule is not None:
        d["rule"] = scenario.rule
    if scenario.is_outline:
        d["isOutline"] = True
    if scenario.outline_name is not None:
        d["outlineName"] = scenario.outline_name
    if scenario.background is not None:
        d["background"] = _background_to_dict(scenario.background, options=options)
    if scenario.retry is not None:
        d["retry"] = dict(scenario.retry)
    d["steps"] = [_step_to_dict(s, options=options) for s in scenario.steps]
    return d


def _feature_to_dict(feature: Feature, *, options: SerializerOptions) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    for sc in feature.scenarios:
        if options.exclude_passed_scenarios and sc.status == STATUS_PASSED:
            continue
        scenarios.append(_scenario_to_dict(sc, options=options))

    d: dict[str, Any] = {
        "id": feature.id,
        "name": feature.name,
        "status": feature.status,
        "duration": feature.duration,
        "scenarios": scenarios,
    }
    if feature.description is not None:
        d["description"] = feature.description
    if feature.tags:
        d["tags"] = list(feature.tags)
    if feature.filename is not None:
        d["filename"] = feature.filename
    if feature.line is not None:
        d["line"] = feature.line
    if feature.background is not None:
        d["background"] = _background_to_dict(feature.background, options=options)
    return d


def _execution_to_dict(execution: Execution) -> dict[str, Any]:
    d: dict[str, Any] = {
        "executionId": execution.execution_id,
        "status": execution.status,
        "duration": execution.duration,
    }
    if execution.project_name is not None:
        d["projectName"] = execution.project_name
    if execution.start_time is not None:
        d["startTime"] = execution.start_time
    if execution.end_time is not None:
        d["endTime"] = execution.end_time
    if execution.command is not None:
        d["command"] = execution.command
    if execution.working_directory is not None:
        d["workingDirectory"] = execution.working_directory
    return d


def _statistics_to_dict(stats: Statistics) -> dict[str, Any]:
    d: dict[str, Any] = {
        "features": stats.features,
        "scenarios": stats.scenarios,
        "steps": stats.steps,
        "passed": stats.passed,
        "failed": stats.failed,
        "skipped": stats.skipped,
        "undefined": stats.undefined,
        "pending": stats.pending,
        "passRate": stats.pass_rate,
        "duration": stats.duration,
        "errorCount": stats.error_count,
        "totalAttachments": stats.total_attachments,
        "totalLogs": stats.total_logs,
        "slowestStepDuration": stats.slowest_step_duration,
        "avgScenarioDuration": stats.avg_scenario_duration,
    }
    if stats.common_exception_type is not None:
        d["commonExceptionType"] = stats.common_exception_type
    if stats.by_tag:
        d["byTag"] = dict(stats.by_tag)
    return d


def _environment_to_dict(env: Environment) -> dict[str, Any]:
    d: dict[str, Any] = {}
    if env.python_version is not None:
        d["pythonVersion"] = env.python_version
    if env.behave_version is not None:
        d["behaveVersion"] = env.behave_version
    if env.platform is not None:
        d["platform"] = env.platform
    if env.os is not None:
        d["os"] = env.os
    if env.os_version is not None:
        d["osVersion"] = env.os_version
    if env.hostname is not None:
        d["hostname"] = env.hostname
    if env.ci_provider is not None:
        d["ciProvider"] = env.ci_provider
    if env.cwd is not None:
        d["cwd"] = env.cwd
    if env.command is not None:
        d["command"] = env.command
    if env.user is not None:
        d["user"] = env.user
    if env.cpu_count is not None:
        d["cpuCount"] = env.cpu_count
    if env.memory_mb is not None:
        d["memoryMb"] = env.memory_mb
    if env.git_branch is not None:
        d["gitBranch"] = env.git_branch
    if env.git_commit is not None:
        d["gitCommit"] = env.git_commit
    if env.git_remote is not None:
        d["gitRemote"] = env.git_remote
    if env.extra:
        d["extra"] = dict(env.extra)
    return d


def _metadata_to_dict(meta: Metadata) -> dict[str, Any]:
    return dict(meta.data) if meta.data else {}


class Serializer:
    """Serialize :class:`ExecutionReport` instances to JSON."""

    def __init__(self, options: SerializerOptions | None = None) -> None:
        self.options = options or SerializerOptions()

    def to_dict(self, report: ExecutionReport) -> dict[str, Any]:
        """Convert ``report`` into a JSON-ready dictionary."""
        opts = self.options

        features: list[dict[str, Any]] = []
        for feature in report.features:
            fd = _feature_to_dict(feature, options=opts)
            if opts.exclude_passed_scenarios and not fd["scenarios"]:
                continue
            features.append(fd)

        root: dict[str, Any] = {
            "schemaVersion": report.schema_version,
            "execution": _execution_to_dict(report.execution),
            "statistics": _statistics_to_dict(report.statistics),
        }
        if opts.include_environment:
            root["environment"] = _environment_to_dict(report.environment)
        root["features"] = features
        root["metadata"] = _metadata_to_dict(report.metadata)
        return root

    def to_json(self, report: ExecutionReport) -> str:
        """Serialize ``report`` to a JSON string."""
        return json.dumps(self.to_dict(report), **self.options.to_json_kwargs())


def serialize(
    report: ExecutionReport,
    *,
    options: SerializerOptions | None = None,
) -> str:
    """Convenience wrapper around :meth:`Serializer.to_json`."""
    return Serializer(options).to_json(report)


__all__ = [
    "Serializer",
    "SerializerOptions",
    "serialize",
]
