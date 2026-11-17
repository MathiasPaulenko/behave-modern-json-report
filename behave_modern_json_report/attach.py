"""High-level attachment helpers for Behave environment.py hooks.

These functions are the recommended way to attach screenshots, files, text
or log messages to the current step. They automatically find the active
``ModernJSONFormatter`` on the Behave context and delegate to it.

Usage in ``environment.py``::

    from behave_modern_json_report import attach_file, attach_screenshot, log

    def after_step(context, step):
        if step.status == "failed":
            attach_screenshot(context, context.driver, name="failure.png")
            log(context, f"URL at failure: {getattr(context, 'url', 'unknown')}")

The helpers are intentionally tolerant to import-time behaviour: the project can
still be installed/tested without Behave being present.
"""

from __future__ import annotations

import base64
import io
import json
import mimetypes
from pathlib import Path
from typing import Any

from .utils import guess_mime


def _find_formatters(context: Any) -> list[Any]:
    """Return every formatter on the Behave context that supports attachments.

    Several compatible formatters may be active at once (e.g. modern JSON plus
    Cucumber JSON, or the same formatter registered twice). Attachments must
    reach all of them so no report silently loses data.

    ``context._runner`` is a weak proxy: once the runner is gone, attribute
    access raises ``ReferenceError`` instead of returning ``None``.
    """
    if context is None:
        return []
    try:
        runner = getattr(context, "_runner", None)
        formatters = getattr(runner, "formatters", None) if runner is not None else None
        if not formatters:
            return []
    except Exception:
        return []
    result: list[Any] = []
    seen: set[int] = set()
    for fmt in formatters:
        try:
            if id(fmt) in seen:
                continue
            if hasattr(fmt, "add_attachment") and hasattr(fmt, "add_log"):
                seen.add(id(fmt))
                result.append(fmt)
        except Exception:
            continue
    return result


def _broadcast_attachment(formatters: list[Any], **kwargs: Any) -> None:
    """Deliver an attachment to every formatter.

    A single misbehaving formatter must not starve the others, so each call
    is isolated.
    """
    for formatter in formatters:
        try:
            formatter.add_attachment(**kwargs)
        except Exception:
            continue


def _broadcast_log(formatters: list[Any], **kwargs: Any) -> None:
    for formatter in formatters:
        try:
            formatter.add_log(**kwargs)
        except Exception:
            continue


def _find_formatter(context: Any) -> Any:
    """Locate the first compatible formatter on the Behave context."""
    formatters = _find_formatters(context)
    return formatters[0] if formatters else None


def attach_file(context: Any, path: str | Path, name: str | None = None) -> None:
    """Attach a file from disk to the current step.

    Args:
        context: Behave context object passed to the hook.
        path: Path to the file to attach.
        name: Optional display name. If omitted, the file name is used.
    """
    formatters = _find_formatters(context)
    if not formatters:
        return
    p = Path(path)
    raw = p.read_bytes()
    data = base64.b64encode(raw).decode("ascii")
    mime = guess_mime(p.name)
    _broadcast_attachment(
        formatters,
        name=name or p.name,
        mime_type=mime,
        content=data,
        encoding="base64",
        size=len(raw),
    )


def attach_text(context: Any, text: str, name: str = "note.txt") -> None:
    """Attach a plain text snippet to the current step.

    Args:
        context: Behave context object passed to the hook.
        text: Raw text to embed.
        name: Display name for the attachment. Defaults to ``note.txt``.
    """
    formatters = _find_formatters(context)
    if not formatters:
        return
    content = str(text)
    _broadcast_attachment(
        formatters,
        name=name,
        mime_type="text/plain",
        content=content,
        encoding="raw",
        size=len(content),
    )


def attach_json(context: Any, data: Any, name: str = "data.json") -> None:
    """Attach a JSON-serializable object to the current step.

    Args:
        context: Behave context object passed to the hook.
        data: Any object that can be passed to ``json.dumps``.
        name: Display name for the attachment. Defaults to ``data.json``.
    """
    formatters = _find_formatters(context)
    if not formatters:
        return
    content = json.dumps(data, indent=2, default=str)
    _broadcast_attachment(
        formatters,
        name=name,
        mime_type="application/json",
        content=content,
        encoding="raw",
        size=len(content),
    )


def _sniff_image_mime(data: bytes) -> str | None:
    """Detect the image format from magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def attach_screenshot(context: Any, source: Any, name: str = "screenshot.png") -> None:
    """Attach a screenshot to the current step.

    The ``source`` argument can be:

    - ``bytes`` or ``bytearray`` -> used as raw PNG data.
    - A path-like string -> read from disk.
    - A Selenium WebDriver instance -> ``driver.get_screenshot_as_png()`` is called.
    - A Playwright Page instance -> ``page.screenshot()`` is called.
    - A PIL Image -> saved to a PNG buffer.

    Args:
        context: Behave context object passed to the hook.
        source: Screenshot source (see above).
        name: Display name for the attachment. Defaults to ``screenshot.png``.
    """
    formatters = _find_formatters(context)
    if not formatters:
        return

    data: bytes | None = None

    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    elif isinstance(source, (str, Path)):
        data = Path(source).read_bytes()
    else:
        method = getattr(source, "get_screenshot_as_png", None)
        if callable(method):
            data = method()
        if data is None:
            method = getattr(source, "screenshot", None)
            if callable(method):
                data = method()
        if data is None:
            save = getattr(source, "save", None)
            if callable(save):
                buf = io.BytesIO()
                save(buf, format="PNG")
                data = buf.getvalue()

    if data is None:
        return
    if not isinstance(data, (bytes, bytearray)):
        # A driver/framework returned something unexpected; keep it attachable
        # instead of crashing inside base64.b64encode.
        data = str(data).encode("utf-8", "replace")

    mime = _sniff_image_mime(bytes(data))
    if mime is None:
        name_lower = name.lower()
        if name_lower.endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        elif name_lower.endswith(".webp"):
            mime = "image/webp"
        elif name_lower.endswith(".gif"):
            mime = "image/gif"
        else:
            mime = mimetypes.guess_type(name)[0] or "image/png"

    encoded = base64.b64encode(bytes(data)).decode("ascii")
    _broadcast_attachment(
        formatters,
        name=name,
        mime_type=mime,
        content=encoded,
        encoding="base64",
        size=len(data),
    )


def log(context: Any, message: str, level: str = "INFO") -> None:
    """Append a log line to the current step.

    Args:
        context: Behave context object passed to the hook.
        message: Free-form text line to attach.
        level: Log level. Defaults to ``INFO``.
    """
    formatters = _find_formatters(context)
    if not formatters:
        return
    text = str(message)
    _broadcast_log(formatters, level=level, message=text)


__all__ = [
    "attach_file",
    "attach_json",
    "attach_screenshot",
    "attach_text",
    "log",
]
