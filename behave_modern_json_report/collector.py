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
    Rule,
    Scenario,
    Statistics,
    Step,
    StepLog,
)
from .schema import SCHEMA_VERSION
from .statistics import compute_statistics, feature_status, rule_status, scenario_status
from .utils import (
    _FAILED_STATUSES,
    STATUS_FAILED,
    STATUS_PASSED,
    generate_id,
    monotonic_seconds,
    normalize_status,
    now_iso,
    safe_str,
    safe_tags,
)


def _map_status(raw: Any) -> str:
    """Map a Behave status (enum or string) to a canonical status string."""
    return normalize_status(raw)


def _behave_status(behave_obj: Any) -> str | None:
    """Return the object's status mapped to canonical form, or ``None``."""
    if behave_obj is None:
        return None
    raw = getattr(behave_obj, "status", None)
    if raw is None:
        return None
    return _map_status(raw)


def _all_steps(behave_scenario: Any) -> list[Any]:
    """Return the scenario's steps including background steps, as a list."""
    all_steps = getattr(behave_scenario, "all_steps", None)
    if all_steps is None:
        all_steps = getattr(behave_scenario, "steps", None) or []
    return list(all_steps)


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
        self._current_rule: Rule | None = None
        self._rule_start: float | None = None
        self._step_start: float | None = None
        self._scenario_start: float | None = None
        self._feature_start: float | None = None

        # Behave emits all ``step()`` events upfront, then ``result()`` events
        # during execution, so results cannot be matched positionally through
        # ``_current_step`` alone.  These structures track the mapping.
        self._behave_feature: Any = None
        self._behave_scenario: Any = None
        self._behave_rule: Any = None
        self._step_lookup: dict[int, Step] = {}
        self._resolved_step_ids: set[int] = set()
        # Attachments/logs added outside a ``result()`` window (hooks, fixtures)
        # are buffered and flushed to the next step that resolves.
        self._pending: list[tuple[str, Any]] = []

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
        self._behave_feature = behave_feature
        self._feature_start = time.monotonic()
        return feature

    def end_feature(self, behave_feature: Any = None) -> Feature | None:
        feature = self._current_feature
        if feature is None:
            return None
        behave_feature = behave_feature or self._behave_feature
        # Finalize any pending rule (which also ends any active scenario)
        if self._current_rule is not None:
            self.end_rule()
        elif self._current_scenario is not None:
            self.end_scenario(None)
        if self._feature_start is not None:
            feature.duration = monotonic_seconds(self._feature_start)
        duration = getattr(behave_feature, "duration", None)
        if duration:
            feature.duration = float(duration)
        feature.status = _behave_status(behave_feature) or feature_status(feature)
        self._current_feature = None
        self._behave_feature = None
        self._feature_start = None
        self._current_rule_name = None
        return feature

    # ------------------------------------------------------------------
    # Rule lifecycle (Gherkin v6 / Behave 1.3.x)
    # ------------------------------------------------------------------

    def start_rule(self, behave_rule: Any) -> Rule | None:
        feature = self._current_feature
        if feature is None:
            return None
        # Finalize previous rule if any
        if self._current_rule is not None:
            self.end_rule()
        rule = Rule(
            id=generate_id("rule"),
            name=safe_str(getattr(behave_rule, "name", "")) or "<unnamed>",
            feature_id=feature.id,
            description=self._join_description(getattr(behave_rule, "description", None)),
            tags=safe_tags(getattr(behave_rule, "tags", None)),
            location=_location(behave_rule),
        )
        behave_background = getattr(behave_rule, "background", None)
        if behave_background:
            rule.background = self._make_background(behave_background)
        feature.rules.append(rule)
        self._current_rule = rule
        self._current_rule_name = rule.name
        self._behave_rule = behave_rule
        self._rule_start = time.monotonic()
        return rule

    def end_rule(self) -> None:
        rule = self._current_rule
        if rule is None:
            return
        # Finalize any active scenario before ending the rule
        if self._current_scenario is not None:
            self.end_scenario(None)
        if self._rule_start is not None:
            rule.duration = monotonic_seconds(self._rule_start)
        duration = getattr(self._behave_rule, "duration", None)
        if duration:
            rule.duration = float(duration)
        rule.status = _behave_status(self._behave_rule) or rule_status(rule)
        self._current_rule = None
        self._current_rule_name = None
        self._behave_rule = None
        self._rule_start = None

    # ------------------------------------------------------------------
    # Scenario lifecycle
    # ------------------------------------------------------------------

    def start_scenario(self, behave_scenario: Any) -> Scenario | None:
        feature = self._current_feature
        if feature is None:
            return None
        # A runtime scenario built from a ScenarioOutline row carries ``_row``
        # and ``parent`` -> ScenarioOutline.  The ``type`` check covers other
        # Behave versions and non-Behave producers.
        row = getattr(behave_scenario, "_row", None)
        parent = getattr(behave_scenario, "parent", None)
        parent_type = safe_str(getattr(parent, "type", ""))
        scenario_type = safe_str(getattr(behave_scenario, "type", ""))
        is_outline = (
            row is not None
            or parent_type == "scenario_outline"
            or scenario_type in ("scenario_outline", "outline", "example")
        )
        outline_name: str | None = None
        if is_outline:
            outline_name = (
                (getattr(parent, "name", None) if parent_type == "scenario_outline" else None)
                or getattr(behave_scenario, "outline_name", None)
                or getattr(behave_scenario, "name", None)
                or None
            )
        rule = self._current_rule
        scenario = Scenario(
            id=generate_id("scenario"),
            name=safe_str(getattr(behave_scenario, "name", "")) or "<unnamed>",
            feature_id=feature.id,
            description=self._join_description(getattr(behave_scenario, "description", None)),
            tags=safe_tags(getattr(behave_scenario, "tags", None)),
            location=_location(behave_scenario),
            examples=self._extract_examples(behave_scenario, row),
            rule=self._current_rule_name,
            rule_id=rule.id if rule is not None else None,
            is_outline=is_outline,
            outline_name=outline_name,
            example_tags=self._extract_example_tags(behave_scenario, parent),
        )
        # Assign background: rule background takes priority, then feature background
        if rule is not None and rule.background:
            scenario.background = rule.background
        elif feature.background:
            scenario.background = feature.background
        feature.scenarios.append(scenario)
        if rule is not None:
            rule.scenarios.append(scenario)
        self._current_scenario = scenario
        self._behave_scenario = behave_scenario
        self._scenario_start = time.monotonic()
        return scenario

    def end_scenario(self, behave_scenario: Any = None) -> Scenario | None:
        scenario = self._current_scenario
        if scenario is None:
            return None
        behave_scenario = behave_scenario or self._behave_scenario
        self._reconcile_steps(scenario, behave_scenario)
        self._sync_background(scenario, behave_scenario)
        # Attachments/logs left dangling (e.g. from after_scenario hooks) go
        # to the last step of the scenario rather than being dropped.
        if self._pending and scenario.steps:
            self._flush_pending(scenario.steps[-1])
        if self._scenario_start is not None:
            scenario.duration = monotonic_seconds(self._scenario_start)
        duration = getattr(behave_scenario, "duration", None)
        if duration:
            scenario.duration = float(duration)
        scenario.status = _behave_status(behave_scenario) or scenario_status(scenario)
        self._current_scenario = None
        self._behave_scenario = None
        self._scenario_start = None
        self._step_lookup.clear()
        self._resolved_step_ids.clear()
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
        self._step_lookup[id(behave_step)] = step
        self._current_step = step
        self._step_start = time.monotonic()
        return step

    def end_step(self, behave_step: Any) -> Step | None:
        # Resolve by behave-step identity: all step() events arrive before any
        # result() events, so _current_step alone cannot route results.
        step = self._step_lookup.get(id(behave_step)) or self._current_step
        if step is None:
            return None
        behave_duration = getattr(behave_step, "duration", None)
        if behave_duration:
            step.duration = float(behave_duration)
        elif self._step_start is not None:
            step.duration = monotonic_seconds(self._step_start)
        step.status = _map_status(getattr(behave_step, "status", STATUS_PASSED))
        step.error = _error_from_step(behave_step)
        self._resolved_step_ids.add(id(step))
        self._flush_pending(step)
        if step is self._current_step:
            self._current_step = None
            self._step_start = None
        return step

    # ------------------------------------------------------------------
    # Attachments + logs
    # ------------------------------------------------------------------

    def _flush_pending(self, step: Step | None) -> None:
        if step is None or not self._pending:
            return
        for kind, item in self._pending:
            if kind == "attachment":
                step.attachments.append(item)
            else:
                step.logs.append(item)
        self._pending.clear()

    def _reconcile_steps(self, scenario: Scenario, behave_scenario: Any) -> None:
        """Apply final Behave statuses to steps that got no ``result()`` event.

        Steps skipped after a failure (or skipped by tags/hooks) never produce
        a result event, but their Behave counterparts still carry a status.
        """
        if behave_scenario is None:
            return
        all_steps = _all_steps(behave_scenario)
        for behave_step in all_steps:
            model_step = self._step_lookup.get(id(behave_step))
            if model_step is None or id(model_step) in self._resolved_step_ids:
                continue
            model_step.status = _map_status(getattr(behave_step, "status", None))
            if model_step.error is None:
                model_step.error = _error_from_step(behave_step)
            duration = getattr(behave_step, "duration", None)
            if duration and not model_step.duration:
                model_step.duration = float(duration)

    def _sync_background(self, scenario: Scenario, behave_scenario: Any) -> None:
        """Copy this run's background step results into the shared definition.

        The ``background`` block captured at feature/rule start is a static
        snapshot; mirror the statuses of the background steps as they actually
        ran inside this scenario.
        """
        background = scenario.background
        if background is None or not background.steps:
            return
        all_steps = _all_steps(behave_scenario) if behave_scenario is not None else None
        behave_background = (
            getattr(behave_scenario, "background", None) if behave_scenario is not None else None
        )
        behave_steps = list(getattr(behave_background, "steps", None) or [])
        if len(behave_steps) != len(background.steps):
            return
        positional = all_steps is not None and len(all_steps) == len(scenario.steps)
        for index, target in enumerate(background.steps):
            source = self._step_lookup.get(id(behave_steps[index]))
            if source is None and positional and index < len(scenario.steps):
                # Outline rows with parametrized backgrounds use per-row step
                # copies; background steps always occupy the first positions.
                source = scenario.steps[index]
            if source is None:
                continue
            target.status = source.status
            target.duration = source.duration
            if source.error is not None:
                target.error = source.error

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
        # Always buffer: during step execution the currently-running Behave
        # step is unknown to the collector, so the item is bound to the next
        # step that resolves (its ``result()`` event follows the hook calls).
        self._pending.append(("attachment", att))
        return att

    def add_log(self, level: str, message: str) -> StepLog | None:
        log = StepLog(timestamp=now_iso(), level=level, message=message)
        self._pending.append(("log", log))
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
    def _extract_examples(behave_scenario: Any, row: Any = None) -> list[dict[str, Any]]:
        # Behave-generated example rows expose ``_row`` (a table Row).
        if row is not None:
            as_dict = getattr(row, "as_dict", None)
            values = dict(as_dict()) if callable(as_dict) else {}
            entry: dict[str, Any] = {"rowId": safe_str(getattr(row, "id", ""))}
            entry.update({safe_str(k): safe_str(v) for k, v in values.items()})
            return [entry]
        examples = getattr(behave_scenario, "examples", None)
        if not examples:
            return []
        if isinstance(examples, list):
            return [dict(e) if isinstance(e, dict) else {"value": safe_str(e)} for e in examples]
        if isinstance(examples, dict):
            return [dict(examples)]
        return [{"value": safe_str(examples)}]

    @staticmethod
    def _extract_example_tags(behave_scenario: Any, parent: Any = None) -> list[str]:
        """Extract tags specific to Example blocks (Gherkin v6)."""
        # behave may expose example-level tags via 'example_tags' or
        # as part of 'effective_tags' minus scenario 'tags'.
        example_tags = getattr(behave_scenario, "example_tags", None)
        if example_tags:
            return safe_tags(example_tags)
        # Runtime rows inherit outline tags + example tags in ``tags``; the
        # difference with the parent outline's tags isolates example tags.
        if getattr(parent, "type", None) == "scenario_outline":
            diff = set(safe_tags(getattr(behave_scenario, "tags", None))) - set(
                safe_tags(getattr(parent, "tags", None))
            )
            return sorted(diff) if diff else []
        # Fallback: compute difference between effective_tags and tags
        effective = getattr(behave_scenario, "effective_tags", None)
        scenario_tags = getattr(behave_scenario, "tags", None)
        if effective and scenario_tags is not None:
            effective_set = set(safe_tags(effective))
            scenario_set = set(safe_tags(scenario_tags))
            diff = effective_set - scenario_set
            return sorted(diff) if diff else []
        return []

    def _overall_status(self) -> str:
        for feature in self._features:
            if feature.status in _FAILED_STATUSES:
                return STATUS_FAILED
            for scenario in feature.scenarios:
                if scenario.status in _FAILED_STATUSES:
                    return STATUS_FAILED
        return STATUS_PASSED


__all__ = ["Collector"]
