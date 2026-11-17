"""Behave Formatter plugin — the entrypoint for ``behave --format``.

Register this formatter in your behave configuration or command line::

    behave --format behave_modern_json_report:ModernJSONFormatter \
           --outfile report.json

The formatter is a thin adapter: it delegates event collection to
:class:`Collector` and serialization to :class:`Serializer`.
"""

from __future__ import annotations

import base64
import contextlib
import json
import mimetypes
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


# ``mjr.``-prefixed userdata keys consumed as formatter options.
_OPTION_KEYS = (
    "pretty",
    "include_environment",
    "include_attachments",
    "embed_attachments",
    "exclude_passed_scenarios",
    "indent",
    "sort_keys",
    "ensure_ascii",
    "include_output",
    "include_background",
    "duration_in_nanos",
)


def _config_option(config: Any, key: str) -> Any:
    """Read a formatter option from ``config``.

    Behave only exposes user configuration to custom formatters through
    ``config.userdata``, so ``mjr.<key>`` is read there first — this is the
    channel documented for production use::

        [behave.userdata]
        mjr.pretty = false

    A ``config.get(key)`` callable is tried afterwards for non-Behave
    producers.
    """
    if config is None:
        return None
    userdata = getattr(config, "userdata", None)
    if isinstance(userdata, dict):
        value = userdata.get(f"mjr.{key}")
        if value is not None:
            return value
    get = getattr(config, "get", None)
    if callable(get):
        with contextlib.suppress(Exception):
            return get(key)
    return None


def _config_bool(config: Any, key: str, default: bool) -> bool:
    raw = _config_option(config, key)
    if raw is None:
        return default
    return _parse_bool(safe_str(raw))


def _options_from_config(config: Any) -> SerializerOptions:
    """Build :class:`SerializerOptions` from a Behave formatter config object."""
    indent = 2
    with contextlib.suppress(Exception):
        indent = max(0, int(safe_str(_config_option(config, "indent"), "2") or "2"))

    return SerializerOptions(
        pretty=_config_bool(config, "pretty", True),
        include_environment=_config_bool(config, "include_environment", True),
        include_attachments=_config_bool(config, "include_attachments", True),
        embed_attachments=_config_bool(config, "embed_attachments", True),
        exclude_passed_scenarios=_config_bool(config, "exclude_passed_scenarios", False),
        indent=indent,
        sort_keys=_config_bool(config, "sort_keys", False),
        ensure_ascii=_config_bool(config, "ensure_ascii", False),
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
    """Read extra metadata from the formatter config.

    Accepts a JSON object string or a dict, via ``mjr.metadata`` in userdata
    or ``config.get("metadata")`` for non-Behave producers::

        [behave.userdata]
        mjr.metadata = {"browser": "firefox", "suite": "nightly"}
    """
    if config is None:
        return {}
    raw = _config_option(config, "metadata")
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        with contextlib.suppress(Exception):
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
    return {}


# ``mjr.``-prefixed userdata keys consumed by the library itself; they must
# not leak into report metadata.
_USERDATA_RESERVED = frozenset({"mjr.project_name", "mjr.metadata"}) | {
    f"mjr.{key}" for key in _OPTION_KEYS
}


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

    name = "modern-json"
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
        else:
            # Bypass base __init__ (programmatic use, or behave missing);
            # keep the attribute so the flush path behaves consistently.
            self.stream_opener = stream_opener
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
        # Finalize previous scenario and feature if any.  The collector keeps
        # a reference to the previous Behave objects, so pass ``None`` here:
        # ``feature`` is the *new* feature, not the one that just ended.
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
        # Finalize previous scenario if any
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
            self._rewrite = False
            return

        # Fallback: write to self._stream or stdout
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


__all__ = ["_BaseFormatter", "ModernJSONFormatter"]
