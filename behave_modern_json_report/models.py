"""Execution model — pure dataclasses with zero Behave dependency.

Every entity carries a stable ``id``.  Optional fields default to ``None`` so
that absent data is represented consistently across serializers.  The model is
designed to be forward-compatible: future fields can be added as optional
without breaking existing consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import (
    STATUS_PASSED,
)

# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Location:
    """A source-code location inside a feature file."""

    filename: str
    line: int
    column: int | None = None


@dataclass(slots=True)
class DocString:
    """A Cucumber/Behave doc-string (triple-quoted block)."""

    content: str
    content_type: str | None = None
    line: int | None = None


@dataclass(slots=True)
class DataTableRow:
    """A single row of a data table."""

    cells: list[str]
    line: int | None = None


@dataclass(slots=True)
class DataTable:
    """A step-level data table."""

    rows: list[DataTableRow] = field(default_factory=list)
    headers: list[str] | None = None


@dataclass(slots=True)
class Error:
    """Structured error representation.

    Never store only a raw string — always provide ``type`` and ``message``.
    ``traceback`` is optional but recommended for debugging surfaces.
    """

    id: str
    type: str
    message: str
    traceback: str | None = None
    location: Location | None = None


@dataclass(slots=True)
class Attachment:
    """An attachment bound to a step.

    Supports both ``embedded`` payloads (base64 for binary, raw for text) and
    ``external`` file references via ``path`` / ``url``.
    """

    id: str
    name: str
    mime_type: str
    encoding: str  # "raw" | "base64" | "external"
    content: str | None = None
    path: str | None = None
    url: str | None = None
    size: int | None = None
    timestamp: str | None = None


@dataclass(slots=True)
class StepLog:
    """A log line captured during step execution."""

    timestamp: str
    level: str
    message: str


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Step:
    """A single step inside a scenario or background."""

    id: str
    keyword: str
    text: str
    status: str = STATUS_PASSED
    duration: float = 0.0
    location: Location | None = None
    error: Error | None = None
    doc_string: DocString | None = None
    data_table: DataTable | None = None
    attachments: list[Attachment] = field(default_factory=list)
    logs: list[StepLog] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Background:
    """A Gherkin background shared by scenarios in a feature or rule."""

    id: str
    name: str = ""
    keyword: str = "Background"
    location: Location | None = None
    steps: list[Step] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Scenario:
    """A scenario (or scenario outline example row) inside a feature."""

    id: str
    name: str
    feature_id: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    location: Location | None = None
    status: str = STATUS_PASSED
    duration: float = 0.0
    steps: list[Step] = field(default_factory=list)
    background: Background | None = None
    rule: str | None = None
    is_outline: bool = False
    outline_name: str | None = None
    retry: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Feature:
    """A Gherkin feature."""

    id: str
    name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    filename: str | None = None
    line: int | None = None
    status: str = STATUS_PASSED
    duration: float = 0.0
    scenarios: list[Scenario] = field(default_factory=list)
    background: Background | None = None


# ---------------------------------------------------------------------------
# Execution + environment + statistics + metadata
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Environment:
    """Runtime environment information."""

    python_version: str | None = None
    behave_version: str | None = None
    platform: str | None = None
    os: str | None = None
    os_version: str | None = None
    hostname: str | None = None
    ci_provider: str | None = None
    cwd: str | None = None
    command: str | None = None
    user: str | None = None
    cpu_count: int | None = None
    memory_mb: int | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    git_remote: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Statistics:
    """Aggregate execution statistics."""

    features: int = 0
    scenarios: int = 0
    steps: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    undefined: int = 0
    pending: int = 0
    pass_rate: float = 0.0
    duration: float = 0.0
    error_count: int = 0
    total_attachments: int = 0
    total_logs: int = 0
    slowest_step_duration: float = 0.0
    avg_scenario_duration: float = 0.0
    common_exception_type: str | None = None
    by_tag: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class Execution:
    """Execution-level metadata."""

    execution_id: str
    project_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration: float = 0.0
    status: str = STATUS_PASSED
    command: str | None = None
    working_directory: str | None = None


@dataclass(slots=True)
class Metadata:
    """Arbitrary user-supplied metadata.

    Stored as a free-form mapping so consumers can attach domain-specific
    context (browser, branch, environment name, etc.).
    """

    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionReport:
    """Root object of the execution model."""

    schema_version: str
    execution: Execution
    statistics: Statistics
    environment: Environment
    features: list[Feature] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)


__all__ = [
    "Attachment",
    "Background",
    "DataTable",
    "DataTableRow",
    "DocString",
    "Environment",
    "Error",
    "Execution",
    "ExecutionReport",
    "Feature",
    "Location",
    "Metadata",
    "Scenario",
    "Statistics",
    "Step",
    "StepLog",
]
