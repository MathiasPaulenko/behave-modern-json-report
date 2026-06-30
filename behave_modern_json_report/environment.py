"""Runtime environment detection.

Builds an :class:`Environment` instance from the current process.  Behave
version is detected lazily so the module remains importable without behave
installed.
"""

from __future__ import annotations

import getpass
import os
import platform as _platform
import subprocess
import sys
from typing import Any

from .models import Environment
from .utils import (
    ci_provider,
    hostname,
    merge_dicts,
    os_name,
    os_version,
    platform_name,
    python_version,
    safe_str,
)


def _behave_version() -> str | None:
    try:
        import behave  # type: ignore[import-not-found]
    except Exception:
        return None
    return safe_str(getattr(behave, "__version__", None)) or None


def _capture_git_info() -> dict[str, str]:
    """Capture git branch, commit and remote if available."""
    info: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            info["commit"] = result.stdout.strip()
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0:
            info["remote"] = result.stdout.strip()
    except Exception:  # pragma: no cover - defensive
        pass
    return info


def detect_environment(
    *,
    behave_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Environment:
    """Build an :class:`Environment` snapshot.

    Parameters
    ----------
    behave_version:
        Override the detected behave version (useful for tests).
    extra:
        Additional environment-specific fields merged into ``Environment.extra``.
    """
    base_extra: dict[str, Any] = {
        "python_implementation": _platform.python_implementation(),
        "machine": _platform.machine() or "unknown",
        "processor": _platform.processor() or "unknown",
    }
    if extra:
        base_extra = merge_dicts(base_extra, extra)

    try:
        cpu_count = os.cpu_count() or 0
    except Exception:  # pragma: no cover
        cpu_count = 0

    memory_mb: int | None = None
    try:
        import psutil  # type: ignore[import-not-found]

        memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        pass

    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover
        user = None

    git_info = _capture_git_info()

    return Environment(
        python_version=python_version(),
        behave_version=behave_version if behave_version is not None else _behave_version(),
        platform=platform_name(),
        os=os_name(),
        os_version=os_version(),
        hostname=hostname(),
        ci_provider=ci_provider(),
        cwd=safe_str(os.getcwd()) or None,
        command=" ".join(sys.argv) or None,
        user=user,
        cpu_count=cpu_count or None,
        memory_mb=memory_mb,
        git_branch=git_info.get("branch") or None,
        git_commit=git_info.get("commit") or None,
        git_remote=git_info.get("remote") or None,
        extra=base_extra,
    )


__all__ = ["detect_environment"]
