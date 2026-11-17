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

import base64
import contextlib
import mimetypes
import os
import sys
from typing import Any

from .collector import Collector
from .cucumber_serializer import (
    CucumberSerializer,
    CucumberSerializerOptions,
)
from .formatter import (
    _BaseFormatter,
    _config_bool,
    _config_option,
    _metadata_from_config,
    _project_name_from_config,
    _userdata_from_config,
)
from .utils import safe_str


def _cucumber_options_from_config(
    config: Any,
) -> CucumberSerializerOptions:
    """Build :class:`CucumberSerializerOptions` from a Behave config object."""
    indent = 2
    with contextlib.suppress(Exception):
        indent = max(0, int(safe_str(_config_option(config, "indent"), "2") or "2"))

    return CucumberSerializerOptions(
        pretty=_config_bool(config, "pretty", True),
        indent=indent,
        sort_keys=_config_bool(config, "sort_keys", False),
        ensure_ascii=_config_bool(config, "ensure_ascii", False),
        embed_attachments=_config_bool(config, "embed_attachments", True),
        include_output=_config_bool(config, "include_output", True),
        include_background=_config_bool(config, "include_background", True),
        duration_in_nanos=_config_bool(config, "duration_in_nanos", True),
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
        else:
            # Bypass base __init__ (programmatic use, or behave missing);
            # keep the attribute so the flush path behaves consistently.
            self.stream_opener = stream_opener
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
        self._rewrite = False

    # ------------------------------------------------------------------
    # Behave lifecycle hooks
    # ------------------------------------------------------------------

    def _reopen_if_closed(self) -> None:
        """Resume accepting events after an ``eof()`` flush.

        ``eof()`` writes the report in programmatic use, but Behave calls it
        once per feature file — producers may keep sending events afterwards.
        Reopening marks the already-written payload stale so the next flush
        rewrites the stream instead of silently dropping the new data.
        """
        if self._closed:
            self._closed = False
            self._rewrite = True

    def uri(self, uri: str) -> None:
        pass

    def feature(self, feature: Any) -> None:
        self._reopen_if_closed()
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(None)
        if self._collector._current_feature is not None:
            self._collector.end_feature(None)
        self._collector.start_feature(feature)

    def background(self, background: Any) -> None:
        pass

    def rule(self, rule: Any) -> None:
        self._reopen_if_closed()
        self._collector.start_rule(rule)

    def rule_finished(self) -> None:
        self._collector.end_rule()

    def scenario(self, scenario: Any) -> None:
        self._reopen_if_closed()
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(None)
        self._collector.start_scenario(scenario)

    def step(self, step: Any) -> None:
        self._reopen_if_closed()
        self._collector.start_step(step)

    def result(self, step: Any) -> None:
        self._reopen_if_closed()
        self._collector.end_step(step)

    # Backward-compatible aliases for programmatic use
    def scenario_result(self, scenario: Any) -> None:
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(scenario)

    def feature_result(self, feature: Any) -> None:
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(None)
        if self._collector._current_feature is not None:
            self._collector.end_feature(feature)

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
            self._rewrite = False
            return

        stream = self._stream or sys.stdout
        if stream is None:
            return
        write = getattr(stream, "write", None)
        if callable(write):
            if self._rewrite:
                # The stream already holds a complete report; rewrite it in
                # place when the stream supports it so the output stays a
                # single JSON document.
                with contextlib.suppress(Exception):
                    stream.seek(0)
                    stream.truncate(0)
                self._rewrite = False
            write(payload)
            write("\n")
            flush = getattr(stream, "flush", None)
            if callable(flush):
                flush()
        else:
            with open(os.fspath(str(stream)), "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.write("\n")

    # ------------------------------------------------------------------
    # Public API for programmatic use
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
    ) -> None:
        self._reopen_if_closed()
        self._collector.add_attachment(
            name=name,
            mime_type=mime_type,
            content=content,
            path=path,
            url=url,
            encoding=encoding,
            size=size,
        )

    def add_log(self, level: str, message: str) -> None:
        self._reopen_if_closed()
        self._collector.add_log(level=level, message=safe_str(message))

    def embedding(self, mime_type: str, data: Any) -> None:
        """Handle ``context.attach(mime_type, data)`` from Behave hooks.

        Behave routes attachments to formatters that expose an ``embedding``
        method; without it the data is silently dropped.
        """
        self._reopen_if_closed()
        if isinstance(data, (bytes, bytearray, memoryview)):
            raw = bytes(data)
        elif data is None:
            raw = b""
        else:
            raw = safe_str(data).encode("utf-8", "replace")
        mime = safe_str(mime_type) or "application/octet-stream"
        extension = mimetypes.guess_extension(mime) or ""
        self._collector.add_attachment(
            name=f"attachment{extension}",
            mime_type=mime,
            content=base64.b64encode(raw).decode("ascii"),
            encoding="base64",
            size=len(raw),
        )
