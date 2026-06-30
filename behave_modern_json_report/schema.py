"""Schema versioning constants for the execution model.

The schema follows Semantic Versioning. Breaking changes require a major
version bump. Additive, backward-compatible changes bump the minor version.
Patch versions are reserved for clarifications and errata that do not change
the structure.
"""

from __future__ import annotations

from pathlib import Path

SCHEMA_VERSION: str = "1.1.0"
"""Canonical schema version shipped with this package."""

SCHEMA_FILE: Path = Path(__file__).resolve().parent / "schemas" / "execution.schema.json"
"""Filesystem path to the bundled JSON Schema."""

__all__ = [
    "SCHEMA_VERSION",
    "SCHEMA_FILE",
]
