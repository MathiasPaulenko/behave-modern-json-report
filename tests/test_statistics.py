"""Unit tests for the statistics aggregator."""

from __future__ import annotations

from behave_modern_json_report.models import (
    Attachment,
    Environment,
    Error,
    Execution,
    ExecutionReport,
    Feature,
    Scenario,
    Statistics,
    Step,
    StepLog,
)
from behave_modern_json_report.schema import SCHEMA_VERSION
from behave_modern_json_report.statistics import compute_statistics, scenario_status
from behave_modern_json_report.utils import (
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    now_iso,
)


def _make_report(features: list[Feature]) -> ExecutionReport:
    return ExecutionReport(
        schema_version=SCHEMA_VERSION,
        execution=Execution(execution_id="exec-1"),
        statistics=Statistics(),
        environment=Environment(),
        features=features,
    )


def _step(status: str = STATUS_PASSED, duration: float = 0.1) -> Step:
    return Step(id="s", keyword="Given", text="step", status=status, duration=duration)


class TestComputeStatistics:
    def test_empty_report(self):
        report = _make_report([])
        stats = compute_statistics(report)
        assert stats.features == 0
        assert stats.scenarios == 0
        assert stats.steps == 0
        assert stats.pass_rate == 0.0

    def test_single_passing_step(self):
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=[_step()])
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.features == 1
        assert stats.scenarios == 1
        assert stats.steps == 1
        assert stats.passed == 1
        assert stats.failed == 0
        assert stats.pass_rate == 1.0

    def test_mixed_statuses(self):
        scenario = Scenario(
            id="sc",
            name="sc",
            feature_id="f",
            steps=[
                _step(STATUS_PASSED),
                _step(STATUS_FAILED),
                _step(STATUS_SKIPPED),
            ],
        )
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.passed == 1
        assert stats.failed == 1
        assert stats.skipped == 1
        assert stats.pass_rate == 0.5


class TestScenarioStatus:
    def test_failed_when_any_step_fails(self):
        sc = Scenario(
            id="sc",
            name="sc",
            feature_id="f",
            steps=[_step(STATUS_PASSED), _step(STATUS_FAILED)],
        )
        assert scenario_status(sc) == STATUS_FAILED

    def test_passed_when_all_pass(self):
        sc = Scenario(
            id="sc",
            name="sc",
            feature_id="f",
            steps=[_step(STATUS_PASSED)],
        )
        assert scenario_status(sc) == STATUS_PASSED

    def test_skipped_when_all_skipped(self):
        sc = Scenario(
            id="sc",
            name="sc",
            feature_id="f",
            steps=[_step(STATUS_SKIPPED)],
        )
        assert scenario_status(sc) == STATUS_SKIPPED


class TestExtendedStatistics:
    def test_error_count(self):
        step = Step(
            id="s1",
            keyword="Given",
            text="fail",
            status=STATUS_FAILED,
            duration=0.1,
            error=Error(id="e1", type="AssertionError", message="boom"),
        )
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=[step])
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.error_count == 1

    def test_total_attachments_and_logs(self):
        att = Attachment(
            id="a1",
            name="screenshot.png",
            mime_type="image/png",
            encoding="base64",
        )
        log = StepLog(timestamp=now_iso(), level="INFO", message="hello")
        step = Step(
            id="s1",
            keyword="Given",
            text="step",
            status=STATUS_PASSED,
            duration=0.1,
            attachments=[att],
            logs=[log],
        )
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=[step])
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.total_attachments == 1
        assert stats.total_logs == 1

    def test_slowest_step_duration(self):
        steps = [
            _step(STATUS_PASSED, 0.1),
            _step(STATUS_PASSED, 0.5),
            _step(STATUS_PASSED, 0.3),
        ]
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=steps)
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.slowest_step_duration == 0.5

    def test_avg_scenario_duration(self):
        sc1 = Scenario(
            id="sc1",
            name="sc1",
            feature_id="f",
            steps=[_step(STATUS_PASSED, 0.2)],
            duration=0.2,
        )
        sc2 = Scenario(
            id="sc2",
            name="sc2",
            feature_id="f",
            steps=[_step(STATUS_PASSED, 0.4)],
            duration=0.4,
        )
        feature = Feature(id="f", name="f", scenarios=[sc1, sc2])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.avg_scenario_duration == 0.3

    def test_common_exception_type(self):
        step1 = Step(
            id="s1",
            keyword="Given",
            text="fail1",
            status=STATUS_FAILED,
            duration=0.1,
            error=Error(id="e1", type="ValueError", message="v"),
        )
        step2 = Step(
            id="s2",
            keyword="When",
            text="fail2",
            status=STATUS_FAILED,
            duration=0.1,
            error=Error(id="e2", type="ValueError", message="v2"),
        )
        step3 = Step(
            id="s3",
            keyword="Then",
            text="fail3",
            status=STATUS_FAILED,
            duration=0.1,
            error=Error(id="e3", type="TypeError", message="t"),
        )
        scenario = Scenario(
            id="sc",
            name="sc",
            feature_id="f",
            steps=[step1, step2, step3],
        )
        feature = Feature(id="f", name="f", scenarios=[scenario])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert stats.common_exception_type == "ValueError"

    def test_by_tag(self):
        sc1 = Scenario(
            id="sc1",
            name="sc1",
            feature_id="f",
            tags=["smoke"],
            steps=[_step(STATUS_PASSED, 0.1)],
        )
        sc2 = Scenario(
            id="sc2",
            name="sc2",
            feature_id="f",
            tags=["regression"],
            steps=[_step(STATUS_FAILED, 0.2)],
        )
        feature = Feature(id="f", name="f", tags=["smoke"], scenarios=[sc1, sc2])
        report = _make_report([feature])
        stats = compute_statistics(report)
        assert "smoke" in stats.by_tag
        assert stats.by_tag["smoke"]["count"] == 2
        assert "regression" in stats.by_tag
        assert stats.by_tag["regression"]["count"] == 1
