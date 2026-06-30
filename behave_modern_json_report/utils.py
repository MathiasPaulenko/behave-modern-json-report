"""Utility helpers: identifiers, timing, safe conversions, status normalization.

These helpers are intentionally Behave-agnostic so they can be reused by the
serializer, validator and external tooling.
"""

from __future__ import annotations

import mimetypes
import os
import platform
import socket
import sys
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Status constants — mirror Behave's full status vocabulary
# ---------------------------------------------------------------------------

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_UNDEFINED = "undefined"
STATUS_PENDING = "pending"
STATUS_UNTESTED = "untested"
STATUS_ERROR = "error"
STATUS_HOOK_ERROR = "hook_error"
STATUS_CLEANUP_ERROR = "cleanup_error"
STATUS_XFAILED = "xfailed"
STATUS_XPASSED = "xpassed"

ALL_STATUSES: tuple[str, ...] = (
    STATUS_PASSED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_UNDEFINED,
    STATUS_PENDING,
    STATUS_UNTESTED,
    STATUS_ERROR,
    STATUS_HOOK_ERROR,
    STATUS_CLEANUP_ERROR,
    STATUS_XFAILED,
    STATUS_XPASSED,
)

_FAILED_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_FAILED,
        STATUS_ERROR,
        STATUS_HOOK_ERROR,
        STATUS_CLEANUP_ERROR,
        STATUS_XFAILED,
    }
)


def normalize_status(value: Any) -> str:
    """Normalize a Behave status (enum or string) to a canonical lowercase string."""
    if value is None:
        return STATUS_UNTESTED
    name = getattr(value, "name", None) or str(value)
    name = name.lower().strip()
    if name in ALL_STATUSES:
        return name
    return STATUS_UNTESTED


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------


def generate_id(prefix: str = "") -> str:
    """Return a stable, unique identifier."""
    value = uuid.uuid4().hex
    return f"{prefix}-{value}" if prefix else value


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def monotonic_seconds(start: float | None = None) -> float:
    """Return elapsed seconds since ``start`` using a monotonic clock."""
    return round(time.monotonic() - (start if start is not None else 0.0), 6)


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    if seconds is None:
        return "0ms"
    if seconds < 1.0:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {int(secs)}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {int(secs)}s"


# ---------------------------------------------------------------------------
# Safe conversions
# ---------------------------------------------------------------------------


def safe_str(value: Any, default: str = "") -> str:
    """Coerce ``value`` to ``str`` without raising."""
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def safe_tags(value: Any) -> list[str]:
    """Normalize tag-like inputs into a de-duplicated list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            items = [value]
    seen: list[str] = []
    for item in items:
        tag = safe_str(item).strip()
        if tag and tag not in seen:
            seen.append(tag)
    return seen


# ---------------------------------------------------------------------------
# MIME type guessing
# ---------------------------------------------------------------------------


def guess_mime(path: str | Path) -> str:
    """Guess the MIME type of a file path."""
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


# ---------------------------------------------------------------------------
# Environment detection helpers
# ---------------------------------------------------------------------------


def python_version() -> str:
    """Return the running Python version as a string."""
    return sys.version.split(" ", 1)[0]


def platform_name() -> str:
    """Return a normalized platform name."""
    return sys.platform


def os_name() -> str:
    """Return a human-readable operating system name."""
    return platform.system() or "Unknown"


def os_version() -> str:
    """Return the operating system release version."""
    return platform.release() or "Unknown"


def hostname() -> str:
    """Return the machine hostname, best-effort."""
    try:
        return socket.gethostname() or "unknown"
    except Exception:
        return "unknown"


def ci_provider() -> str | None:
    """Detect the current CI provider from environment variables."""
    env = os.environ
    if env.get("GITHUB_ACTIONS") == "true":
        return "github-actions"
    if env.get("GITLAB_CI"):
        return "gitlab-ci"
    if env.get("JENKINS_URL"):
        return "jenkins"
    if env.get("CIRCLECI"):
        return "circleci"
    if env.get("TRAVIS"):
        return "travis-ci"
    if env.get("BUILDKITE"):
        return "buildkite"
    if env.get("TF_BUILD"):
        return "azure-pipelines"
    if env.get("BITBUCKET_BUILD_NUMBER"):
        return "bitbucket-pipelines"
    if env.get("DRONE"):
        return "drone"
    if env.get("CI") and env.get("CI_NAME"):
        return safe_str(env.get("CI_NAME")).lower() or "ci"
    if env.get("CI"):
        return "ci"
    return None


def merge_dicts(base: dict[str, Any], extra: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow merge of ``base`` and ``extra`` (``extra`` wins)."""
    if not extra:
        return dict(base)
    merged = dict(base)
    merged.update(extra)
    return merged


__all__ = [
    "ALL_STATUSES",
    "STATUS_CLEANUP_ERROR",
    "STATUS_ERROR",
    "STATUS_FAILED",
    "STATUS_HOOK_ERROR",
    "STATUS_PASSED",
    "STATUS_PENDING",
    "STATUS_SKIPPED",
    "STATUS_UNDEFINED",
    "STATUS_UNTESTED",
    "STATUS_XFAILED",
    "STATUS_XPASSED",
    "_FAILED_STATUSES",
    "ci_provider",
    "format_duration",
    "generate_id",
    "guess_mime",
    "hostname",
    "merge_dicts",
    "monotonic_seconds",
    "normalize_status",
    "now_iso",
    "os_name",
    "os_version",
    "platform_name",
    "python_version",
    "safe_str",
    "safe_tags",
]
