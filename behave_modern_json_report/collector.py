"""Collector — adapts Behave runtime events into the execution model.

The collector is the **only** module that depends on Behave.  It receives
high-level objects (``Feature``, ``Scenario``, ``Step``) from the formatter
and builds :class:`ExecutionReport` instances without leaking Behave types
into the model.
"""

from __future__ import annotations

import os
import time
import traceback as _tb
from typing import Any

from .environment import detect_environment
from .models import (
    Attachment,
    Background,
    DataTable,
    DataTableRow,
    DocString,
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
from .schema import SCHEMA_VERSION
from .statistics import compute_statistics, feature_status, scenario_status
from .utils import (
    STATUS_PASSED,
    STATUS_UNTESTED,
    generate_id,
    monotonic_seconds,
    now_iso,
    safe_str,
    safe_tags,
)

_BEHAVE_STATUS_MAP = {
    "passed": "passed",
    "failed": "failed",
    "skipped": "skipped",
    "undefined": "undefined",
    "untested": "untested",
    "pending": "pending",
    "error": "error",
    "hook_error": "hook_error",
    "cleanup_error": "cleanup_error",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
}


def _map_status(raw: Any) -> str:
    """Map a Behave status to a canonical status string."""
    if raw is None:
        return STATUS_UNTESTED
    name = getattr(raw, "name", None) or str(raw)
    key = name.lower().strip()
    return _BEHAVE_STATUS_MAP.get(key, key or STATUS_PASSED)


def _location(obj: Any) -> Location | None:
    filename = getattr(obj, "filename", None)
    line = getattr(obj, "line", None)
    if filename is None and line is None:
        location = getattr(obj, "location", None)
        if location is not None:
            filename = getattr(location, "filename", None)
            line = getattr(location, "line", None)
    if filename is None and line is None:
        return None
    return Location(filename=safe_str(filename), line=int(line or 0))


def _doc_string(raw: Any) -> DocString | None:
    if raw is None:
        return None
    content = getattr(raw, "value", None) or getattr(raw, "content", None)
    if content is None:
        return None
    content_type = getattr(raw, "content_type", None) or getattr(raw, "contentType", None)
    line = getattr(raw, "line", None)
    return DocString(
        content=safe_str(content),
        content_type=safe_str(content_type) or None,
        line=line,
    )


def _data_table(raw: Any) -> DataTable | None:
    if raw is None:
        return None
    rows_obj = getattr(raw, "rows", None)
    if rows_obj is None:
        return None
    rows: list[DataTableRow] = []
    for row in rows_obj:
        cells = [safe_str(c) for c in (getattr(row, "cells", None) or [])]
        line = getattr(row, "line", None)
        rows.append(DataTableRow(cells=cells, line=line))
    headers: list[str] | None = None
    headings = getattr(raw, "headings", None)
    if headings:
        headers = [safe_str(h) for h in headings]
    return DataTable(rows=rows, headers=headers)


def _error_from_step(step: Any) -> Error | None:
    exc = getattr(step, "error", None)
    if exc is None:
        exc = getattr(step, "exception", None)
    if exc is None:
        error_message = getattr(step, "error_message", None)
        if error_message:
            return Error(
                id=generate_id("err"),
                type="Error",
                message=safe_str(error_message),
                traceback=safe_str(getattr(step, "exc_traceback", None) or error_message),
                location=_location(step),
            )
        return None
    if isinstance(exc, Error):
        return exc
    if isinstance(exc, BaseException):
        tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
        return Error(
            id=generate_id("err"),
            type=type(exc).__name__,
            message=safe_str(exc),
            traceback=tb,
            location=_location(step),
        )
    return Error(
        id=generate_id("err"),
        type="Error",
        message=safe_str(exc),
        location=_location(step),
    )


class Collector:
    """Accumulates Behave events into an :class:`ExecutionReport`.

    The collector is stateful.  Create one per formatter run, feed it events,
    then call :meth:`finalize` to obtain the report.
    """

    def __init__(
        self,
        *,
        project_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        behave_version: str | None = None,
    ) -> None:
        self._project_name = project_name
        self._metadata = dict(metadata) if metadata else {}
        self._behave_version = behave_version

        self._execution_id = generate_id("exec")
        self._start_time = now_iso()
        self._start_monotonic = time.monotonic()
        self._command: str | None = None
        self._working_directory: str | None = os.getcwd()

        self._features: list[Feature] = []
        self._current_feature: Feature | None = None
        self._current_scenario: Scenario | None = None
        self._current_step: Step | None = None
        self._current_rule_name: str | None = None
        self._step_start: float | None = None
        self._scenario_start: float | None = None
        self._feature_start: float | None = None

    # ------------------------------------------------------------------
    # Feature lifecycle
    # ------------------------------------------------------------------

    def start_feature(self, behave_feature: Any) -> Feature:
        feature = Feature(
            id=generate_id("feature"),
            name=safe_str(getattr(behave_feature, "name", "")) or "<unnamed>",
            description=self._join_description(getattr(behave_feature, "description", None)),
            tags=safe_tags(getattr(behave_feature, "tags", None)),
            filename=getattr(behave_feature, "filename", None),
            line=getattr(behave_feature, "line", None),
        )
        behave_background = getattr(behave_feature, "background", None)
        if behave_background:
            feature.background = self._make_background(behave_background)
        self._features.append(feature)
        self._current_feature = feature
        self._feature_start = time.monotonic()
        return feature

    def end_feature(self, behave_feature: Any) -> Feature | None:
        feature = self._current_feature
        if feature is None:
            return None
        if self._feature_start is not None:
            feature.duration = monotonic_seconds(self._feature_start)
        feature.status = feature_status(feature)
        self._current_feature = None
        self._feature_start = None
        self._current_rule_name = None
        return feature

    # ------------------------------------------------------------------
    # Rule lifecycle (Gherkin v6 / Behave 1.3.x)
    # ------------------------------------------------------------------

    def start_rule(self, behave_rule: Any) -> None:
        self._current_rule_name = safe_str(getattr(behave_rule, "name", "")) or None

    def end_rule(self) -> None:
        self._current_rule_name = None

    # ------------------------------------------------------------------
    # Scenario lifecycle
    # ------------------------------------------------------------------

    def start_scenario(self, behave_scenario: Any) -> Scenario | None:
        feature = self._current_feature
        if feature is None:
            return None
        scenario_type = safe_str(getattr(behave_scenario, "type", ""))
        is_outline = scenario_type in ("scenario_outline", "outline")
        outline_name: str | None = None
        if is_outline:
            outline_name = (
                getattr(behave_scenario, "outline_name", None)
                or getattr(behave_scenario, "name", None)
                or None
            )
        scenario = Scenario(
            id=generate_id("scenario"),
            name=safe_str(getattr(behave_scenario, "name", "")) or "<unnamed>",
            feature_id=feature.id,
            description=self._join_description(getattr(behave_scenario, "description", None)),
            tags=safe_tags(getattr(behave_scenario, "tags", None)),
            location=_location(behave_scenario),
            examples=self._extract_examples(behave_scenario),
            rule=self._current_rule_name,
            is_outline=is_outline,
            outline_name=outline_name,
        )
        if feature.background:
            scenario.background = feature.background
        feature.scenarios.append(scenario)
        self._current_scenario = scenario
        self._scenario_start = time.monotonic()
        return scenario

    def end_scenario(self, behave_scenario: Any) -> Scenario | None:
        scenario = self._current_scenario
        if scenario is None:
            return None
        if self._scenario_start is not None:
            scenario.duration = monotonic_seconds(self._scenario_start)
        scenario.status = scenario_status(scenario)
        self._current_scenario = None
        self._scenario_start = None
        return scenario

    # ------------------------------------------------------------------
    # Step lifecycle
    # ------------------------------------------------------------------

    def start_step(self, behave_step: Any) -> Step | None:
        scenario = self._current_scenario
        if scenario is None:
            return None
        step = Step(
            id=generate_id("step"),
            keyword=safe_str(getattr(behave_step, "keyword", "")),
            text=safe_str(getattr(behave_step, "name", ""))
            or safe_str(getattr(behave_step, "text", "")),
            location=_location(behave_step),
            doc_string=_doc_string(getattr(behave_step, "doc_string", None)),
            data_table=_data_table(getattr(behave_step, "table", None)),
        )
        scenario.steps.append(step)
        self._current_step = step
        self._step_start = time.monotonic()
        return step

    def end_step(self, behave_step: Any) -> Step | None:
        step = self._current_step
        if step is None:
            return None
        if self._step_start is not None:
            step.duration = monotonic_seconds(self._step_start)
        step.status = _map_status(getattr(behave_step, "status", STATUS_PASSED))
        step.error = _error_from_step(behave_step)
        self._current_step = None
        self._step_start = None
        return step

    # ------------------------------------------------------------------
    # Attachments + logs
    # ------------------------------------------------------------------

    def add_attachment(
        self,
        *,
        name: str,
        mime_type: str,
        content: str | None = None,
        path: str | None = None,
        url: str | None = None,
        encoding: str = "raw",
        size: int | None = None,
    ) -> Attachment | None:
        step = self._current_step
        if step is None:
            return None
        att = Attachment(
            id=generate_id("att"),
            name=name,
            mime_type=mime_type,
            encoding=encoding,
            content=content,
            path=path,
            url=url,
            size=size,
            timestamp=now_iso(),
        )
        step.attachments.append(att)
        return att

    def add_log(self, level: str, message: str) -> StepLog | None:
        step = self._current_step
        if step is None:
            return None
        log = StepLog(timestamp=now_iso(), level=level, message=message)
        step.logs.append(log)
        return log

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def set_command(self, command: str) -> None:
        self._command = command

    def finalize(self) -> ExecutionReport:
        end_time = now_iso()
        duration = monotonic_seconds(self._start_monotonic)
        execution = Execution(
            execution_id=self._execution_id,
            project_name=self._project_name,
            start_time=self._start_time,
            end_time=end_time,
            duration=duration,
            status=self._overall_status(),
            command=self._command,
            working_directory=self._working_directory,
        )
        environment = detect_environment(
            behave_version=self._behave_version,
            extra=self._metadata.get("environment_extra"),
        )
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=execution,
            statistics=Statistics(),
            environment=environment,
            features=self._features,
            metadata=Metadata(data=dict(self._metadata)),
        )
        report.statistics = compute_statistics(report)
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_background(behave_background: Any) -> Background:
        bg = Background(
            id=generate_id("bg"),
            name=safe_str(getattr(behave_background, "name", "")) or "",
            keyword=safe_str(getattr(behave_background, "keyword", "Background")) or "Background",
            location=_location(behave_background),
        )
        for behave_step in getattr(behave_background, "steps", []) or []:
            step = Step(
                id=generate_id("step"),
                keyword=safe_str(getattr(behave_step, "keyword", "")),
                text=safe_str(getattr(behave_step, "name", ""))
                or safe_str(getattr(behave_step, "text", "")),
                status=_map_status(getattr(behave_step, "status", STATUS_PASSED)),
                duration=float(getattr(behave_step, "duration", 0.0) or 0.0),
                location=_location(behave_step),
                doc_string=_doc_string(getattr(behave_step, "doc_string", None)),
                data_table=_data_table(getattr(behave_step, "table", None)),
            )
            error = _error_from_step(behave_step)
            if error:
                step.error = error
            bg.steps.append(step)
        return bg

    @staticmethod
    def _join_description(desc: Any) -> str | None:
        if desc is None:
            return None
        if isinstance(desc, str):
            return desc or None
        if isinstance(desc, list):
            joined = "\n".join(safe_str(d) for d in desc)
            return joined or None
        return safe_str(desc) or None

    @staticmethod
    def _extract_examples(behave_scenario: Any) -> list[dict[str, Any]]:
        examples = getattr(behave_scenario, "examples", None)
        if not examples:
            return []
        if isinstance(examples, list):
            return [dict(e) if isinstance(e, dict) else {"value": safe_str(e)} for e in examples]
        if isinstance(examples, dict):
            return [dict(examples)]
        return [{"value": safe_str(examples)}]

    def _overall_status(self) -> str:
        for feature in self._features:
            if feature.status == "failed":
                return "failed"
            for scenario in feature.scenarios:
                if scenario.status == "failed":
                    return "failed"
        return STATUS_PASSED


__all__ = ["Collector"]
