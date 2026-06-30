"""Behave Formatter plugin — the entrypoint for ``behave --format``.

Register this formatter in your behave configuration or command line::

    behave --format behave_modern_json_report:ModernJSONFormatter \
           --outfile report.json

The formatter is a thin adapter: it delegates event collection to
:class:`Collector` and serialization to :class:`Serializer`.
"""

from __future__ import annotations

import contextlib
import os
import sys
from typing import Any

try:
    from behave.formatter.base import Formatter as _BaseFormatter  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    _BaseFormatter = object  # type: ignore[misc,assignment,unused-ignore]

from .collector import Collector
from .serializer import Serializer, SerializerOptions
from .utils import safe_str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _options_from_config(config: Any) -> SerializerOptions:
    """Build :class:`SerializerOptions` from a Behave formatter config object."""
    pretty = True
    include_environment = True
    include_attachments = True
    embed_attachments = True
    exclude_passed_scenarios = False
    indent = 2
    sort_keys = False
    ensure_ascii = False

    if config is not None:
        get = getattr(config, "get", None)
        if callable(get):
            with contextlib.suppress(Exception):
                pretty = _parse_bool(get("pretty", "true"))
            with contextlib.suppress(Exception):
                include_environment = _parse_bool(get("include_environment", "true"))
            with contextlib.suppress(Exception):
                include_attachments = _parse_bool(get("include_attachments", "true"))
            with contextlib.suppress(Exception):
                embed_attachments = _parse_bool(get("embed_attachments", "true"))
            with contextlib.suppress(Exception):
                exclude_passed_scenarios = _parse_bool(get("exclude_passed_scenarios", "false"))
            with contextlib.suppress(Exception):
                indent = int(get("indent", "2"))
            with contextlib.suppress(Exception):
                sort_keys = _parse_bool(get("sort_keys", "false"))
            with contextlib.suppress(Exception):
                ensure_ascii = _parse_bool(get("ensure_ascii", "false"))

    return SerializerOptions(
        pretty=pretty,
        include_environment=include_environment,
        include_attachments=include_attachments,
        embed_attachments=embed_attachments,
        exclude_passed_scenarios=exclude_passed_scenarios,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=ensure_ascii,
    )


def _project_name_from_config(config: Any) -> str | None:
    """Read ``mjr.project_name`` from a Behave formatter config or userdata."""
    if config is None:
        return None
    # First try the formatter config section
    get = getattr(config, "get", None)
    if callable(get):
        with contextlib.suppress(Exception):
            value = get("project_name", "")
            if value and value.strip():
                return str(value.strip())
    # Then try userdata (from [behave.userdata] or --userdata)
    userdata = getattr(config, "userdata", None)
    if isinstance(userdata, dict):
        value = userdata.get("mjr.project_name")
        if value and str(value).strip():
            return str(value).strip()
    return None


def _metadata_from_config(config: Any) -> dict[str, Any]:
    """Read ``metadata`` from a Behave formatter config object.

    The value must be a JSON object string, e.g.::

        metadata = {"branch": "dev", "team": "qa"}
    """
    if config is None:
        return {}
    get = getattr(config, "get", None)
    if not callable(get):
        return {}
    with contextlib.suppress(Exception):
        import json

        raw = get("metadata", "")
        if raw and raw.strip():
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    return {}


# Keys that behave itself puts in userdata; we don't want them in report metadata.
_USERDATA_RESERVED = frozenset(
    {
        "mjr.project_name",
    }
)


def _userdata_from_config(config: Any) -> dict[str, Any]:
    """Read behave's ``config.userdata`` as report metadata.

    Only keys prefixed with ``mjr.`` are included. The prefix is stripped
    in the resulting metadata. For example::

        [behave.userdata]
        mjr.project_name = My Project
        mjr.branch = dev
        mjr.team = qa

    produces ``{"branch": "dev", "team": "qa"}`` in metadata (project_name
    is handled separately).
    """
    if config is None:
        return {}
    userdata = getattr(config, "userdata", None)
    if not isinstance(userdata, dict):
        return {}
    result: dict[str, Any] = {}
    for key, value in userdata.items():
        str_key = str(key)
        if not str_key.startswith("mjr."):
            continue
        if str_key in _USERDATA_RESERVED:
            continue
        result[str_key[len("mjr.") :]] = value
    return result


class ModernJSONFormatter(_BaseFormatter):  # type: ignore[misc]
    """Behave formatter that writes a modern JSON execution report.

    Behave expects formatters to implement a subset of the following methods.
    We implement the common lifecycle hooks and ignore those we do not need.
    """

    name = "json-modern"
    description = "Modern JSON execution report for Behave"

    def __init__(
        self,
        stream_opener: Any = None,
        config: Any = None,
        *,
        stream: Any = None,
        options: SerializerOptions | None = None,
        project_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if _BaseFormatter is not object and stream_opener is not None:
            super().__init__(stream_opener, config)
        elif _BaseFormatter is not object:
            # Bypass base __init__ that requires a stream_opener
            pass
        self._stream = stream or sys.stdout
        self._config = config
        self._options = options or _options_from_config(config)

        # Build metadata: userdata as base, explicit metadata overrides it.
        resolved_metadata = _userdata_from_config(config)
        resolved_metadata.update(_metadata_from_config(config))
        if metadata:
            resolved_metadata.update(metadata)

        self._collector = Collector(
            project_name=project_name or _project_name_from_config(config),
            metadata=resolved_metadata,
        )
        self._serializer = Serializer(self._options)
        self._closed = False

    # ------------------------------------------------------------------
    # Behave lifecycle hooks
    # ------------------------------------------------------------------

    def uri(self, uri: str) -> None:
        pass

    def feature(self, feature: Any) -> None:
        # Finalize previous scenario and feature if any
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
        # Finalize previous scenario if any
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(scenario)
        self._collector.start_scenario(scenario)

    def step(self, step: Any) -> None:
        self._collector.start_step(step)

    def result(self, step: Any) -> None:
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
        # Behave calls eof() after each feature file.
        # Finalize any remaining scenario/feature for this file.
        if self._collector._current_scenario is not None:
            self._collector.end_scenario(None)
        if self._collector._current_feature is not None:
            self._collector.end_feature(None)
        # In behave, close() is the final write point (stream_opener is set).
        # In programmatic use, eof() is the flush point (no stream_opener).
        if getattr(self, "stream_opener", None) is None:
            self._flush()
            self._closed = True

    def close(self) -> None:
        # close() is called once at the very end — write the report.
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

        # Use behave's stream_opener if available
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

        # Fallback: write to self._stream or stdout
        stream = self._stream or sys.stdout
        if stream is None:
            return
        write = getattr(stream, "write", None)
        if callable(write):
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
        self._collector.add_log(level=level, message=safe_str(message))


__all__ = ["_BaseFormatter", "ModernJSONFormatter"]
