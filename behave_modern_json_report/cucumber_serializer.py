"""Cucumber JSON serializer — converts the execution model to Cucumber JSON format.

Produces a JSON array of Feature objects compatible with the de facto Cucumber
JSON report standard used by cucumber-jvm, cucumber-js, cucumber-ruby, and tools
like cucumber-reporting, multiple-cucumber-html-reporter, and ReportPortal.

The serializer has **no** dependency on Behave. It operates exclusively on the
dataclasses defined in :mod:`behave_modern_json_report.models`.

See: https://github.com/cucumber/cucumber-json-schema
"""

from __future__ import annotations

import base64
import json
from typing import Any

from .models import (
    Attachment,
    Background,
    DataTable,
    DocString,
    ExecutionReport,
    Feature,
    Scenario,
    Step,
)

# ---------------------------------------------------------------------------
# Status mapping — our expanded statuses → Cucumber's canonical set
# ---------------------------------------------------------------------------

_CUCUMBER_STATUS_MAP = {
    "passed": "passed",
    "failed": "failed",
    "skipped": "skipped",
    "undefined": "undefined",
    "pending": "pending",
    "untested": "skipped",
    "error": "failed",
    "hook_error": "failed",
    "cleanup_error": "failed",
    "xfailed": "skipped",
    "xpassed": "passed",
}


def _cucumber_status(status: str) -> str:
    """Map our status to the closest Cucumber status."""
    return _CUCUMBER_STATUS_MAP.get(status, "undefined")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class CucumberSerializerOptions:
    """Configuration for the Cucumber JSON serializer."""

    def __init__(
        self,
        *,
        pretty: bool = True,
        indent: int = 2,
        sort_keys: bool = False,
        ensure_ascii: bool = False,
        embed_attachments: bool = True,
        include_output: bool = True,
        include_hooks: bool = True,
        include_background: bool = True,
        duration_in_nanos: bool = True,
    ) -> None:
        self.pretty = pretty
        self.indent = indent
        self.sort_keys = sort_keys
        self.ensure_ascii = ensure_ascii
        self.embed_attachments = embed_attachments
        self.include_output = include_output
        self.include_hooks = include_hooks
        self.include_background = include_background
        self.duration_in_nanos = duration_in_nanos


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _duration(value: float, *, nanos: bool) -> int:
    """Convert seconds (float) to nanoseconds (int) or keep as seconds."""
    if nanos:
        return int(value * 1_000_000_000)
    return int(value)


def _location_str(location: Any) -> str | None:
    """Build a Cucumber-style location string like 'features/foo.feature:42'."""
    if location is None:
        return None
    filename = getattr(location, "filename", None)
    line = getattr(location, "line", None)
    if filename is None:
        return None
    if line is not None:
        return f"{filename}:{line}"
    return str(filename)


def _tags_to_cucumber(tags: list[str]) -> list[dict[str, Any]]:
    """Convert tag strings to Cucumber tag objects."""
    return [{"name": tag} for tag in tags]


def _step_match(step: Step) -> dict[str, Any]:
    """Build the Cucumber ``match`` object for a step."""
    match: dict[str, Any] = {}
    location = _location_str(step.location)
    if location:
        match["location"] = location
    # Arguments — we don't capture step arguments from behave, but the
    # field is expected by some consumers. Leave empty if unknown.
    match["arguments"] = []
    return match


def _step_result(step: Step, *, nanos: bool) -> dict[str, Any]:
    """Build the Cucumber ``result`` object for a step."""
    result: dict[str, Any] = {
        "status": _cucumber_status(step.status),
        "duration": _duration(step.duration, nanos=nanos),
    }
    if step.error is not None:
        error_parts = []
        if step.error.type:
            error_parts.append(step.error.type)
        if step.error.message:
            error_parts.append(step.error.message)
        if step.error.traceback:
            error_parts.append(step.error.traceback)
        if error_parts:
            result["error_message"] = "\n".join(error_parts)
    return result


def _doc_string_to_cucumber(doc: DocString | None) -> dict[str, Any] | None:
    """Convert a DocString to Cucumber's ``doc_string`` object."""
    if doc is None:
        return None
    obj: dict[str, Any] = {
        "value": doc.content,
        "line": doc.line if doc.line is not None else 0,
    }
    if doc.content_type is not None:
        obj["content_type"] = doc.content_type
    return obj


def _data_table_to_cucumber(table: DataTable | None) -> list[dict[str, Any]] | None:
    """Convert a DataTable to Cucumber's ``rows`` array."""
    if table is None or not table.rows:
        return None
    return [{"cells": row.cells} for row in table.rows]


def _attachments_to_embeddings(
    attachments: list[Attachment], *, embed: bool
) -> list[dict[str, Any]] | None:
    """Convert attachments to Cucumber ``embeddings`` array."""
    if not attachments:
        return None
    if not embed:
        return None
    embeddings: list[dict[str, Any]] = []
    for att in attachments:
        emb: dict[str, Any] = {
            "mime_type": att.mime_type,
        }
        if att.name:
            emb["name"] = att.name
        if att.encoding == "base64" and att.content:
            emb["data"] = att.content
        elif att.encoding == "raw" and att.content is not None:
            emb["data"] = base64.b64encode(att.content.encode("utf-8")).decode("ascii")
        elif att.content is not None:
            emb["data"] = att.content
        elif att.path:
            emb["data"] = att.path
        embeddings.append(emb)
    return embeddings


def _logs_to_output(logs: list[Any]) -> list[str] | None:
    """Convert step logs to Cucumber ``output`` array."""
    if not logs:
        return None
    return [f"[{log.level}] {log.message}" if hasattr(log, "level") else str(log) for log in logs]


# ---------------------------------------------------------------------------
# Step / Element / Feature converters
# ---------------------------------------------------------------------------


def _step_to_cucumber(step: Step, *, options: CucumberSerializerOptions) -> dict[str, Any]:
    """Convert a model Step to a Cucumber step dict."""
    d: dict[str, Any] = {
        "keyword": step.keyword,
        "name": step.text,
        "line": step.location.line if step.location else 0,
        "match": _step_match(step),
        "result": _step_result(step, nanos=options.duration_in_nanos),
    }

    doc_string = _doc_string_to_cucumber(step.doc_string)
    if doc_string is not None:
        d["doc_string"] = doc_string

    rows = _data_table_to_cucumber(step.data_table)
    if rows is not None:
        d["rows"] = rows

    if options.embed_attachments:
        embeddings = _attachments_to_embeddings(step.attachments, embed=True)
        if embeddings is not None:
            d["embeddings"] = embeddings

    if options.include_output:
        output = _logs_to_output(step.logs)
        if output is not None:
            d["output"] = output

    return d


def _background_to_element(
    bg: Background | None,
    *,
    options: CucumberSerializerOptions,
) -> dict[str, Any] | None:
    """Convert a Background to a Cucumber element with type='background'."""
    if bg is None or not bg.steps:
        return None
    return {
        "keyword": bg.keyword,
        "name": bg.name,
        "description": "",
        "type": "background",
        "line": bg.location.line if bg.location else 0,
        "steps": [_step_to_cucumber(s, options=options) for s in bg.steps],
    }


def _scenario_to_element(
    scenario: Scenario,
    *,
    options: CucumberSerializerOptions,
) -> dict[str, Any]:
    """Convert a model Scenario to a Cucumber element dict."""
    element: dict[str, Any] = {
        "id": scenario.id,
        "keyword": "Scenario Outline" if scenario.is_outline else "Scenario",
        "name": scenario.name,
        "description": scenario.description or "",
        "type": "scenario",
        "line": scenario.location.line if scenario.location else 0,
        "tags": _tags_to_cucumber(scenario.tags),
        "steps": [_step_to_cucumber(s, options=options) for s in scenario.steps],
    }

    if scenario.is_outline and scenario.outline_name:
        element["name"] = scenario.outline_name

    return element


def _feature_to_cucumber(
    feature: Feature,
    *,
    options: CucumberSerializerOptions,
) -> dict[str, Any]:
    """Convert a model Feature to a Cucumber feature dict."""
    elements: list[dict[str, Any]] = []

    # Background as first element
    if options.include_background and feature.background is not None:
        bg_element = _background_to_element(feature.background, options=options)
        if bg_element is not None:
            elements.append(bg_element)

    # Scenarios
    for scenario in feature.scenarios:
        elements.append(_scenario_to_element(scenario, options=options))

    return {
        "uri": feature.filename or "",
        "id": feature.id,
        "keyword": "Feature",
        "name": feature.name,
        "description": feature.description or "",
        "line": feature.line or 0,
        "tags": _tags_to_cucumber(feature.tags),
        "elements": elements,
    }


# ---------------------------------------------------------------------------
# Main serializer
# ---------------------------------------------------------------------------


class CucumberSerializer:
    """Serialize an :class:`ExecutionReport` to Cucumber JSON format."""

    def __init__(self, options: CucumberSerializerOptions | None = None) -> None:
        self._options = options or CucumberSerializerOptions()

    def to_list(self, report: ExecutionReport) -> list[dict[str, Any]]:
        """Convert an ExecutionReport to a list of Cucumber feature dicts."""
        return [_feature_to_cucumber(feature, options=self._options) for feature in report.features]

    def to_json(self, report: ExecutionReport) -> str:
        """Serialize an ExecutionReport to a Cucumber JSON string."""
        data = self.to_list(report)
        if self._options.pretty:
            return json.dumps(
                data,
                indent=self._options.indent,
                sort_keys=self._options.sort_keys,
                ensure_ascii=self._options.ensure_ascii,
            )
        return json.dumps(
            data,
            sort_keys=self._options.sort_keys,
            ensure_ascii=self._options.ensure_ascii,
            separators=(",", ":"),
        )


def serialize_cucumber(
    report: ExecutionReport,
    options: CucumberSerializerOptions | None = None,
) -> str:
    """Serialize an ExecutionReport to Cucumber JSON format."""
    return CucumberSerializer(options).to_json(report)


__all__ = [
    "CucumberSerializer",
    "CucumberSerializerOptions",
    "serialize_cucumber",
]
