"""Cucumber JSON Formatter — Behave formatter that outputs Cucumber-compatible JSON.

This formatter reuses the same :class:`Collector` as :class:`ModernJSONFormatter`
but serializes the execution model to the de facto Cucumber JSON report format,
enabling compatibility with tools that consume Cucumber JSON (e.g.
cucumber-reporting, multiple-cucumber-html-reporter, ReportPortal, Jenkins
plugins, etc.).

Usage::

    behave --format behave_modern_json_report:CucumberJSONFormatter \\
        --outfile cucumber.json
"""

from __future__ import annotations

import contextlib
import sys
from typing import Any

from .collector import Collector
from .cucumber_serializer import (
    CucumberSerializer,
    CucumberSerializerOptions,
)
from .formatter import (
    _BaseFormatter,
    _metadata_from_config,
    _parse_bool,
    _project_name_from_config,
    _userdata_from_config,
)


def _cucumber_options_from_config(
    config: Any,
) -> CucumberSerializerOptions:
    """Build :class:`CucumberSerializerOptions` from a Behave config object."""
    pretty = True
    indent = 2
    sort_keys = False
    ensure_ascii = False
    embed_attachments = True
    include_output = True
    include_hooks = True
    include_background = True
    duration_in_nanos = True

    if config is not None:
        get = getattr(config, "get", None)
        if callable(get):
            with contextlib.suppress(Exception):
                pretty = _parse_bool(get("pretty", "true"))
            with contextlib.suppress(Exception):
                indent = int(get("indent", "2"))
            with contextlib.suppress(Exception):
                sort_keys = _parse_bool(get("sort_keys", "false"))
            with contextlib.suppress(Exception):
                ensure_ascii = _parse_bool(get("ensure_ascii", "false"))
            with contextlib.suppress(Exception):
                embed_attachments = _parse_bool(get("embed_attachments", "true"))
            with contextlib.suppress(Exception):
                include_output = _parse_bool(get("include_output", "true"))
            with contextlib.suppress(Exception):
                include_hooks = _parse_bool(get("include_hooks", "true"))
            with contextlib.suppress(Exception):
                include_background = _parse_bool(get("include_background", "true"))
            with contextlib.suppress(Exception):
                duration_in_nanos = _parse_bool(get("duration_in_nanos", "true"))

    return CucumberSerializerOptions(
        pretty=pretty,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=ensure_ascii,
        embed_attachments=embed_attachments,
        include_output=include_output,
        include_hooks=include_hooks,
        include_background=include_background,
        duration_in_nanos=duration_in_nanos,
    )


class CucumberJSONFormatter(_BaseFormatter):  # type: ignore[misc]
    """Behave formatter that writes a Cucumber-compatible JSON report.

    Behave expects formatters to implement a subset of the following methods.
    We implement the common lifecycle hooks and ignore those we do not need.
    """

    name = "cucumber-json"
    description = "Cucumber-compatible JSON report for Behave"

    def __init__(
        self,
        stream_opener: Any = None,
        config: Any = None,
        *,
        stream: Any = None,
        options: CucumberSerializerOptions | None = None,
        project_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if _BaseFormatter is not object and stream_opener is not None:
            super().__init__(stream_opener, config)
        elif _BaseFormatter is not object:
            pass
        self._stream = stream or sys.stdout
        self._config = config
        self._options = options or _cucumber_options_from_config(config)

        # Build metadata: userdata as base, explicit metadata overrides it.
        resolved_metadata = _userdata_from_config(config)
        resolved_metadata.update(_metadata_from_config(config))
        if metadata:
            resolved_metadata.update(metadata)

        self._collector = Collector(
            project_name=project_name or _project_name_from_config(config),
            metadata=resolved_metadata,
        )
        self._serializer = CucumberSerializer(self._options)
        self._closed = False

    # ------------------------------------------------------------------
    # Behave lifecycle hooks
    # ------------------------------------------------------------------

    def uri(self, uri: str) -> None:
        pass

    def feature(self, feature: Any) -> None:
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(feature)
        if self._collector._current_feature is not None:
            self._collector.end_feature(feature)
        self._collector.start_feature(feature)

    def background(self, background: Any) -> None:
        pass

    def rule(self, rule: Any) -> None:
        self._collector.start_rule(rule)

    def scenario(self, scenario: Any) -> None:
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(scenario)
        self._collector.start_scenario(scenario)

    def step(self, step: Any) -> None:
        self._collector.start_step(step)

    def result(self, step: Any) -> None:
        self._collector.end_step(step)

    def eof(self) -> None:
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(None)
        if self._collector._current_feature is not None:
            self._collector.end_feature(None)
        if getattr(self, "stream_opener", None) is None:
            self._flush()
            self._closed = True

    def close(self) -> None:
        self._flush()
        self._closed = True

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        if self._closed:
            return
        report = self._collector.finalize()
        payload = self._serializer.to_json(report)

        stream_opener = getattr(self, "stream_opener", None)
        if stream_opener is not None:
            stream = stream_opener.open()
            stream.write(payload)
            stream.write("\n")
            if hasattr(stream, "flush"):
                stream.flush()
            if hasattr(stream_opener, "close"):
                stream_opener.close()
            return

        stream = self._stream or sys.stdout
        if stream is None:
            return
        write = getattr(stream, "write", None)
        if callable(write):
            write(payload)
            write("\n")
