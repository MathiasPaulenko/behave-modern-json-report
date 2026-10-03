"""Statistics aggregation over an :class:`ExecutionReport` model.

The aggregator walks features → scenarios → steps and produces a
:class:`Statistics` instance.  It is pure and Behave-agnostic.
"""

from __future__ import annotations

from typing import Any

from .models import ExecutionReport, Feature, Rule, Scenario, Statistics
from .utils import (
    _FAILED_STATUSES,
    ALL_STATUSES,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    STATUS_UNDEFINED,
    STATUS_UNTESTED,
)

_STATUS_FIELDS = {
    STATUS_PASSED: "passed",
    STATUS_FAILED: "failed",
    STATUS_SKIPPED: "skipped",
    STATUS_UNDEFINED: "undefined",
    STATUS_PENDING: "pending",
}


def _tag_stats() -> dict[str, Any]:
    """Return a fresh counters dict for a single tag."""
    stats: dict[str, Any] = {"count": 0, "duration": 0.0}
    stats.update(dict.fromkeys(ALL_STATUSES, 0))
    return stats


def compute_statistics(report: ExecutionReport) -> Statistics:
    """Compute aggregate statistics for ``report``."""
    features = 0
    scenarios = 0
    steps = 0
    counts: dict[str, int] = dict.fromkeys(_STATUS_FIELDS.values(), 0)
    total_duration = 0.0
    error_count = 0
    total_attachments = 0
    total_logs = 0
    slowest_step_duration = 0.0
    all_durations: list[float] = []
    exception_counts: dict[str, int] = {}
    by_tag: dict[str, dict[str, Any]] = {}

    for feature in report.features:
        features += 1
        feature_duration = 0.0

        # The collector appends every scenario to feature.scenarios,
        # including those that also belong to a rule.  Iterate the
        # single list to avoid double-counting.
        for scenario in feature.scenarios:
            scenarios += 1
            scenario_duration = 0.0

            for step in scenario.steps:
                steps += 1
                field_name = _STATUS_FIELDS.get(step.status)
                if field_name is not None:
                    counts[field_name] += 1
                scenario_duration += step.duration or 0.0
                if step.status in _FAILED_STATUSES:
                    error_count += 1
                total_attachments += len(step.attachments)
                total_logs += len(step.logs)
                slowest_step_duration = max(slowest_step_duration, step.duration)
                if step.error and step.error.type:
                    exception_counts[step.error.type] = exception_counts.get(step.error.type, 0) + 1

            scenario.duration = scenario.duration or scenario_duration
            all_durations.append(scenario.duration)
            feature_duration += scenario.duration

            # Tag statistics
            for tag in set(scenario.tags) | set(feature.tags):
                tag_data = by_tag.setdefault(tag, _tag_stats())
                tag_data["count"] += 1
                tag_data["duration"] += scenario.duration
                if scenario.status in tag_data:
                    tag_data[scenario.status] += 1

        feature.duration = feature.duration or feature_duration
        total_duration += feature.duration

    total_terminal = counts["passed"] + counts["failed"]
    pass_rate = (counts["passed"] / total_terminal) if total_terminal else 0.0
    avg_scenario_duration = (sum(all_durations) / len(all_durations)) if all_durations else 0.0
    common_exception_type = (
        max(exception_counts, key=lambda k: exception_counts.get(k, 0))
        if exception_counts
        else None
    )

    return Statistics(
        features=features,
        scenarios=scenarios,
        steps=steps,
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        undefined=counts["undefined"],
        pending=counts["pending"],
        pass_rate=round(pass_rate, 6),
        duration=round(total_duration, 6),
        error_count=error_count,
        total_attachments=total_attachments,
        total_logs=total_logs,
        slowest_step_duration=round(slowest_step_duration, 6),
        avg_scenario_duration=round(avg_scenario_duration, 6),
        common_exception_type=common_exception_type,
        by_tag=by_tag,
    )


def _derive_status(statuses: list[str]) -> str:
    """Derive an entity status from child statuses.

    Mirrors Behave's semantics: an ``undefined`` or ``pending`` step marks the
    scenario as ``error`` (it is reported as an errored scenario by Behave).
    """
    if any(s in _FAILED_STATUSES for s in statuses):
        return STATUS_FAILED
    if any(s in (STATUS_UNDEFINED, STATUS_PENDING) for s in statuses):
        return STATUS_ERROR
    if statuses and all(s == STATUS_SKIPPED for s in statuses):
        return STATUS_SKIPPED
    if any(s == STATUS_UNTESTED for s in statuses):
        return STATUS_UNTESTED
    return STATUS_PASSED


def feature_status(feature: Feature) -> str:
    """Derive a feature status from its scenarios.

    The collector appends every scenario to ``feature.scenarios``,
    including those that also belong to a rule, so iterating the
    single list is sufficient.
    """
    return _derive_status([s.status for s in feature.scenarios])


def scenario_status(scenario: Scenario) -> str:
    """Derive a scenario status from its steps."""
    return _derive_status([s.status for s in scenario.steps])


def rule_status(rule: Rule) -> str:
    """Derive a rule status from its scenarios."""
    return _derive_status([s.status for s in rule.scenarios])


__all__ = [
    "compute_statistics",
    "feature_status",
    "rule_status",
    "scenario_status",
]
