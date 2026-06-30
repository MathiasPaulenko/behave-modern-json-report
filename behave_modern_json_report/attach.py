"""High-level attachment helpers for Behave environment.py hooks.

These functions are the recommended way to attach screenshots, files, text
or log messages to the current step. They automatically find the active
``ModernJSONFormatter`` on the Behave context and delegate to it.

Usage in ``environment.py``::

    from behave_modern_json_report import attach_file, attach_screenshot, log

    def after_step(context, step):
        if step.status == "failed":
            attach_screenshot(context, name="failure.png")
            log(context, f"URL at failure: {getattr(context, 'url', 'unknown')}")

The helpers are intentionally tolerant to import-time behaviour: the project can
still be installed/tested without Behave being present.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .utils import guess_mime


def _find_formatter(context: Any) -> Any:
    """Locate the ModernJSONFormatter instance on the Behave context."""
    if context is None:
        return None
    runner = getattr(context, "_runner", None)
    if runner is None:
        return None
    formatters = getattr(runner, "formatters", None)
    if not formatters:
        return None
    for fmt in formatters:
        if hasattr(fmt, "add_attachment") and hasattr(fmt, "add_log"):
            return fmt
    return None


def attach_file(context: Any, path: str | Path, name: str | None = None) -> None:
    """Attach a file from disk to the current step.

    Args:
        context: Behave context object passed to the hook.
        path: Path to the file to attach.
        name: Optional display name. If omitted, the file name is used.
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return
    p = Path(path)
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    mime = guess_mime(p.name)
    formatter.add_attachment(
        name=name or p.name,
        mime_type=mime,
        content=data,
        encoding="base64",
        size=p.stat().st_size,
    )


def attach_text(context: Any, text: str, name: str = "note.txt") -> None:
    """Attach a plain text snippet to the current step.

    Args:
        context: Behave context object passed to the hook.
        text: Raw text to embed.
        name: Display name for the attachment. Defaults to ``note.txt``.
    """
    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.add_attachment(
        name=name,
        mime_type="text/plain",
        content=str(text),
        encoding="raw",
    )


def attach_json(context: Any, data: Any, name: str = "data.json") -> None:
    """Attach a JSON-serializable object to the current step.

    Args:
        context: Behave context object passed to the hook.
        data: Any object that can be passed to ``json.dumps``.
        name: Display name for the attachment. Defaults to ``data.json``.
    """
    import json

    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.add_attachment(
        name=name,
        mime_type="application/json",
        content=json.dumps(data, indent=2, default=str),
        encoding="raw",
    )


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
    formatter = _find_formatter(context)
    if formatter is None:
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
                import io

                buf = io.BytesIO()
                save(buf, format="PNG")
                data = buf.getvalue()

    if data is None:
        return

    name_lower = name.lower()
    if name_lower.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif name_lower.endswith(".webp"):
        mime = "image/webp"
    elif name_lower.endswith(".gif"):
        mime = "image/gif"
    else:
        mime = mimetypes.guess_type(name)[0] or "image/png"

    formatter.add_attachment(
        name=name,
        mime_type=mime,
        content=base64.b64encode(data).decode("ascii"),
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
    formatter = _find_formatter(context)
    if formatter is None:
        return
    formatter.add_log(level=level, message=str(message))


__all__ = [
    "attach_file",
    "attach_json",
    "attach_screenshot",
    "attach_text",
    "log",
]
