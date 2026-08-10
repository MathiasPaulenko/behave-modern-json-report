"""Regression tests for bugs found during the Phase 2 static audit.

Each test corresponds to a specific bug fix:
1. _FAILED_STATUSES incorrectly included 'xfailed'
2. CucumberJSONFormatter missing add_attachment / add_log
3. CucumberJSONFormatter._flush missing flush + file-path fallback
4. CucumberSerializerOptions.include_hooks was dead code
5. Structural validator didn't validate rules array
6. pyproject.toml missing schemas subpackage declaration
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from behave_modern_json_report.cucumber_formatter import CucumberJSONFormatter
from behave_modern_json_report.cucumber_serializer import (
    CucumberSerializerOptions,
)
from behave_modern_json_report.models import (
    Environment,
    Execution,
    ExecutionReport,
    Feature,
    Location,
    Metadata,
    Rule,
    Scenario,
    Statistics,
    Step,
)
from behave_modern_json_report.schema import SCHEMA_VERSION
from behave_modern_json_report.statistics import feature_status, scenario_status
from behave_modern_json_report.utils import (
    _FAILED_STATUSES,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_XFAILED,
)


def _behave_feature(name="Feature 1", tags=None, filename="f.feature", line=1):
    return SimpleNamespace(
        name=name,
        tags=tags or [],
        filename=filename,
        line=line,
        description=None,
    )


def _behave_rule(name="Rule 1", tags=None, filename="f.feature", line=2):
    return SimpleNamespace(
        name=name,
        tags=tags or [],
        filename=filename,
        line=line,
        description=None,
        background=None,
    )


def _behave_scenario(name="Scenario 1", tags=None, filename="f.feature", line=3):
    return SimpleNamespace(
        name=name,
        tags=tags or [],
        filename=filename,
        line=line,
        description=None,
        examples=None,
    )


def _behave_step(keyword="Given", text="a step", status="passed", filename="f.feature", line=5):
    return SimpleNamespace(
        keyword=keyword,
        name=text,
        status=status,
        filename=filename,
        line=line,
        error=None,
        doc_string=None,
        table=None,
    )


# ---------------------------------------------------------------------------
# Bug 1: _FAILED_STATUSES must not include 'xfailed'
# ---------------------------------------------------------------------------


class TestXfailedNotFailure:
    def test_xfailed_not_in_failed_statuses(self):
        assert STATUS_XFAILED not in _FAILED_STATUSES

    def test_xfailed_scenario_status_is_passed(self):
        """An xfailed-only scenario should not be marked as failed."""
        step = Step(
            id="s1",
            keyword="Given",
            text="step",
            status=STATUS_XFAILED,
            duration=0.1,
        )
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=[step])
        assert scenario_status(scenario) != STATUS_FAILED

    def test_xfailed_feature_status_is_passed(self):
        """A feature with only xfailed scenarios should not be marked as failed."""
        step = Step(
            id="s1",
            keyword="Given",
            text="step",
            status=STATUS_XFAILED,
            duration=0.1,
        )
        scenario = Scenario(id="sc", name="sc", feature_id="f", steps=[step])
        feature = Feature(id="f", name="f", scenarios=[scenario])
        assert feature_status(feature) != STATUS_FAILED


# ---------------------------------------------------------------------------
# Bug 2: CucumberJSONFormatter must have add_attachment and add_log
# ---------------------------------------------------------------------------


class TestCucumberFormatterAttachments:
    def test_has_add_attachment(self):
        fmt = CucumberJSONFormatter(stream=__import__("io").StringIO())
        assert hasattr(fmt, "add_attachment")

    def test_has_add_log(self):
        fmt = CucumberJSONFormatter(stream=__import__("io").StringIO())
        assert hasattr(fmt, "add_log")

    def test_add_attachment_works(self):
        import io

        fmt = CucumberJSONFormatter(stream=io.StringIO())
        # Simulate a step being in progress
        fmt._collector.start_feature(_make_feature_ns())
        fmt._collector.start_scenario(_make_scenario_ns())
        fmt._collector.start_step(_make_step_ns())
        fmt.add_attachment(name="test.txt", mime_type="text/plain", content="hello", encoding="raw")
        fmt._collector.end_step(_make_step_ns())
        fmt._collector.end_scenario(None)
        fmt._collector.end_feature(None)
        report = fmt._collector.finalize()
        assert report.features[0].scenarios[0].steps[0].attachments
        assert report.features[0].scenarios[0].steps[0].attachments[0].name == "test.txt"

    def test_add_log_works(self):
        import io

        fmt = CucumberJSONFormatter(stream=io.StringIO())
        fmt._collector.start_feature(_make_feature_ns())
        fmt._collector.start_scenario(_make_scenario_ns())
        fmt._collector.start_step(_make_step_ns())
        fmt.add_log("INFO", "test log message")
        fmt._collector.end_step(_make_step_ns())
        fmt._collector.end_scenario(None)
        fmt._collector.end_feature(None)
        report = fmt._collector.finalize()
        assert report.features[0].scenarios[0].steps[0].logs
        assert report.features[0].scenarios[0].steps[0].logs[0].message == "test log message"


# ---------------------------------------------------------------------------
# Bug 3: CucumberJSONFormatter._flush must flush and support file-path fallback
# ---------------------------------------------------------------------------


class TestCucumberFormatterFlush:
    def test_flush_to_string_io_calls_flush(self):
        import io

        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream)
        fmt._collector.start_feature(_make_feature_ns())
        fmt._collector.start_scenario(_make_scenario_ns())
        fmt._collector.start_step(_make_step_ns())
        fmt._collector.end_step(_make_step_ns())
        fmt._collector.end_scenario(None)
        fmt._collector.end_feature(None)
        fmt._flush()
        assert stream.getvalue()  # Something was written


# ---------------------------------------------------------------------------
# Bug 4: CucumberSerializerOptions must not have include_hooks
# ---------------------------------------------------------------------------


class TestNoDeadIncludeHooks:
    def test_include_hooks_not_in_options(self):
        opts = CucumberSerializerOptions()
        assert not hasattr(opts, "include_hooks")

    def test_include_hooks_not_accepted_in_constructor(self):
        import inspect

        sig = inspect.signature(CucumberSerializerOptions.__init__)
        assert "include_hooks" not in sig.parameters


# ---------------------------------------------------------------------------
# Bug 5: Structural validator must validate rules array
# ---------------------------------------------------------------------------


def _make_feature_ns():
    return SimpleNamespace(name="F", tags=[], filename="f.feature", line=1, description=None)


def _make_scenario_ns():
    return SimpleNamespace(
        name="S",
        tags=[],
        filename="f.feature",
        line=3,
        description=None,
        examples=None,
    )


def _make_step_ns():
    return SimpleNamespace(
        keyword="Given",
        name="step",
        status="passed",
        filename="f.feature",
        line=5,
    )


def _make_report_with_rules() -> ExecutionReport:
    step = Step(
        id="step-1",
        keyword="Given",
        text="a step",
        status=STATUS_PASSED,
        duration=0.1,
        location=Location(filename="f.feature", line=5),
    )
    scenario = Scenario(
        id="sc-1",
        name="S",
        feature_id="f-1",
        status=STATUS_PASSED,
        duration=0.1,
        steps=[step],
    )
    rule = Rule(
        id="rule-1",
        name="My Rule",
        feature_id="f-1",
        status=STATUS_PASSED,
        duration=0.1,
        scenarios=[scenario],
    )
    feature = Feature(
        id="f-1",
        name="F",
        status=STATUS_PASSED,
        duration=0.1,
        scenarios=[scenario],
        rules=[rule],
    )
    return ExecutionReport(
        schema_version=SCHEMA_VERSION,
        execution=Execution(execution_id="exec-1", status=STATUS_PASSED, duration=0.1),
        statistics=Statistics(),
        environment=Environment(),
        features=[feature],
        metadata=Metadata(),
    )


class TestStructuralValidatorRules:
    def test_valid_rules_pass_structural_validation(self):
        """The structural validator (fallback) should accept valid rules."""
        from behave_modern_json_report.serializer import Serializer

        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        # Force structural validation by calling _structural_validate directly
        from behave_modern_json_report.validator import ValidationResult, _structural_validate

        result = ValidationResult(valid=True)
        _structural_validate(data, result)
        assert result.valid, [str(e) for e in result.errors]

    def test_rule_missing_id_caught_by_structural_validator(self):
        """The structural validator should catch a missing rule id."""
        from behave_modern_json_report.serializer import Serializer

        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        del data["features"][0]["rules"][0]["id"]
        from behave_modern_json_report.validator import ValidationResult, _structural_validate

        result = ValidationResult(valid=True)
        _structural_validate(data, result)
        assert not result.valid
        assert any("id" in e.path for e in result.errors)

    def test_rule_missing_name_caught_by_structural_validator(self):
        """The structural validator should catch a missing rule name."""
        from behave_modern_json_report.serializer import Serializer

        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        del data["features"][0]["rules"][0]["name"]
        from behave_modern_json_report.validator import ValidationResult, _structural_validate

        result = ValidationResult(valid=True)
        _structural_validate(data, result)
        assert not result.valid
        assert any("name" in e.path for e in result.errors)


# ---------------------------------------------------------------------------
# Bug 6: schemas subpackage must be importable and declared
# ---------------------------------------------------------------------------


class TestSchemasSubpackage:
    def test_schemas_subpackage_importable(self):
        import behave_modern_json_report.schemas as schemas_pkg

        assert hasattr(schemas_pkg, "__path__")

    def test_schema_file_located_via_package(self):
        from pathlib import Path

        import behave_modern_json_report.schemas as schemas_pkg

        schema_path = Path(schemas_pkg.__path__[0]) / "execution.schema.json"
        assert schema_path.exists()
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert data["title"] == "Behave Modern JSON Report - Execution"


# ---------------------------------------------------------------------------
# Bug 9: exclude_passed_scenarios must also filter rule scenarios
# ---------------------------------------------------------------------------


class TestExcludePassedScenariosRules:
    def test_passed_rule_scenarios_excluded(self):
        """When exclude_passed_scenarios is True, passed scenarios inside
        rules must also be excluded, not just top-level feature scenarios.
        """
        from behave_modern_json_report.serializer import (
            Serializer,
            SerializerOptions,
        )

        passed_step = Step(id="s1", keyword="Given", text="ok", status=STATUS_PASSED, duration=0.1)
        failed_step = Step(id="s2", keyword="Then", text="bad", status=STATUS_FAILED, duration=0.1)
        passed_sc = Scenario(
            id="sc-passed",
            name="P",
            feature_id="f",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        failed_sc = Scenario(
            id="sc-failed",
            name="F",
            feature_id="f",
            status=STATUS_FAILED,
            duration=0.1,
            steps=[failed_step],
        )
        rule = Rule(
            id="r1",
            name="R",
            feature_id="f",
            status=STATUS_FAILED,
            duration=0.2,
            scenarios=[passed_sc, failed_sc],
        )
        feature = Feature(
            id="f",
            name="F",
            status=STATUS_FAILED,
            duration=0.2,
            scenarios=[passed_sc, failed_sc],
            rules=[rule],
        )
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e", status=STATUS_FAILED, duration=0.2),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )

        opts = SerializerOptions(exclude_passed_scenarios=True)
        data = Serializer(opts).to_dict(report)

        feat = data["features"][0]
        # Top-level scenarios: only failed should remain
        top_ids = [s["id"] for s in feat["scenarios"]]
        assert "sc-passed" not in top_ids
        assert "sc-failed" in top_ids

        # Rule scenarios: only failed should remain
        rule_ids = [s["id"] for s in feat["rules"][0]["scenarios"]]
        assert "sc-passed" not in rule_ids
        assert "sc-failed" in rule_ids


# ---------------------------------------------------------------------------
# Bug 10: end_rule does not finalize active scenario before ending the rule
# ---------------------------------------------------------------------------


class TestEndRuleFinalizesScenario:
    def test_end_rule_ends_active_scenario(self):
        """When end_rule is called while a scenario is still active,
        the scenario must be finalized (status and duration set) before
        the rule ends.
        """
        from behave_modern_json_report.collector import Collector

        c = Collector()
        f = _behave_feature()
        c.start_feature(f)
        r = _behave_rule()
        c.start_rule(r)
        sc = _behave_scenario()
        c.start_scenario(sc)
        step = _behave_step()
        c.start_step(step)
        c.end_step(step)
        # Don't call end_scenario — end_rule should handle it
        c.end_rule()
        c.end_feature(f)
        report = c.finalize()

        rule = report.features[0].rules[0]
        scenario = rule.scenarios[0]
        assert scenario.status == STATUS_PASSED
        assert scenario.duration >= 0.0
        assert rule.status == STATUS_PASSED


# ---------------------------------------------------------------------------
# Bug 11: end_feature does not finalize active scenario when no rule is active
# ---------------------------------------------------------------------------


class TestEndFeatureFinalizesScenario:
    def test_end_feature_ends_active_scenario_no_rule(self):
        """When end_feature is called while a scenario is still active
        and no rule is active, the scenario must be finalized.
        """
        from behave_modern_json_report.collector import Collector

        c = Collector()
        f = _behave_feature()
        c.start_feature(f)
        sc = _behave_scenario()
        c.start_scenario(sc)
        step = _behave_step()
        c.start_step(step)
        c.end_step(step)
        # Don't call end_scenario — end_feature should handle it
        c.end_feature(f)
        report = c.finalize()

        scenario = report.features[0].scenarios[0]
        assert scenario.status == STATUS_PASSED
        assert scenario.duration >= 0.0


# ---------------------------------------------------------------------------
# Bug 12: feature_status with rule scenarios (regression protection)
# ---------------------------------------------------------------------------


class TestFeatureStatusChecksRuleScenarios:
    def test_failed_rule_scenario_marks_feature_failed(self):
        """A failed scenario that belongs to a rule should cause
        feature_status to return 'failed'.

        The collector adds rule scenarios to both feature.scenarios and
        rule.scenarios, so feature_status only needs to check
        feature.scenarios.
        """
        from behave_modern_json_report.models import Feature, Rule
        from behave_modern_json_report.statistics import feature_status
        from behave_modern_json_report.utils import STATUS_FAILED, STATUS_PASSED

        passed_step = Step(
            id="s1",
            keyword="Given",
            text="pass",
            status=STATUS_PASSED,
            duration=0.1,
        )
        failed_step = Step(
            id="s2",
            keyword="When",
            text="fail",
            status=STATUS_FAILED,
            duration=0.1,
        )
        passed_scenario = Scenario(
            id="sc1",
            name="Top",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        failed_rule_scenario = Scenario(
            id="sc2",
            name="Rule scenario",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.1,
            steps=[failed_step],
        )
        rule = Rule(
            id="r1",
            name="Rule 1",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.1,
            scenarios=[failed_rule_scenario],
        )
        # Collector adds rule scenarios to feature.scenarios too
        feature = Feature(
            id="f1",
            name="Feature 1",
            status=STATUS_PASSED,
            duration=0.2,
            scenarios=[passed_scenario, failed_rule_scenario],
            rules=[rule],
        )

        assert feature_status(feature) == STATUS_FAILED

    def test_all_passed_rule_scenarios_feature_passed(self):
        """All passed scenarios (top-level and rule) should yield 'passed'."""
        from behave_modern_json_report.models import Feature, Rule
        from behave_modern_json_report.statistics import feature_status
        from behave_modern_json_report.utils import STATUS_PASSED

        passed_step = Step(
            id="s1",
            keyword="Given",
            text="pass",
            status=STATUS_PASSED,
            duration=0.1,
        )
        passed_scenario = Scenario(
            id="sc1",
            name="Top",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        rule = Rule(
            id="r1",
            name="Rule 1",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            scenarios=[passed_scenario],
        )
        feature = Feature(
            id="f1",
            name="Feature 1",
            status=STATUS_PASSED,
            duration=0.2,
            scenarios=[passed_scenario],
            rules=[rule],
        )

        assert feature_status(feature) == STATUS_PASSED


# ---------------------------------------------------------------------------
# Bug 13: compute_statistics with rule scenarios (regression protection)
# ---------------------------------------------------------------------------


class TestComputeStatisticsCountsRuleScenarios:
    def test_rule_scenarios_counted_in_statistics(self):
        """Scenarios that belong to rules must be counted in statistics.

        The collector adds rule scenarios to both feature.scenarios and
        rule.scenarios, so compute_statistics only needs to iterate
        feature.scenarios to count all scenarios exactly once.
        """
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Rule,
        )
        from behave_modern_json_report.statistics import compute_statistics
        from behave_modern_json_report.utils import STATUS_FAILED, STATUS_PASSED

        passed_step = Step(
            id="s1",
            keyword="Given",
            text="pass",
            status=STATUS_PASSED,
            duration=0.1,
        )
        failed_step = Step(
            id="s2",
            keyword="When",
            text="fail",
            status=STATUS_FAILED,
            duration=0.2,
        )
        top_scenario = Scenario(
            id="sc1",
            name="Top",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        rule_scenario = Scenario(
            id="sc2",
            name="Rule scenario",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.2,
            steps=[failed_step],
        )
        rule = Rule(
            id="r1",
            name="Rule 1",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.2,
            scenarios=[rule_scenario],
        )
        # Collector adds rule scenarios to feature.scenarios too
        feature = Feature(
            id="f1",
            name="Feature 1",
            status=STATUS_FAILED,
            duration=0.3,
            scenarios=[top_scenario, rule_scenario],
            rules=[rule],
        )
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e1", status=STATUS_FAILED),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )

        stats = compute_statistics(report)
        # 2 scenarios: 1 top-level + 1 rule (both in feature.scenarios)
        assert stats.scenarios == 2
        # 2 steps: 1 in top scenario + 1 in rule scenario
        assert stats.steps == 2
        # 1 passed step (top) + 1 failed step (rule)
        assert stats.passed == 1
        assert stats.failed == 1
        # 1 error from the failed step
        assert stats.error_count == 1


# ---------------------------------------------------------------------------
# Bug 14: _overall_status only checked STATUS_FAILED, not all failed statuses
# ---------------------------------------------------------------------------


class TestOverallStatusChecksAllFailedStatuses:
    """_overall_status should return STATUS_FAILED for any status in
    _FAILED_STATUSES (failed, error, hook_error, cleanup_error), not
    just STATUS_FAILED.
    """

    @pytest.mark.parametrize("status", ["failed", "error", "hook_error", "cleanup_error"])
    def test_error_status_marks_overall_failed(self, status):
        from behave_modern_json_report.collector import Collector
        from behave_modern_json_report.utils import STATUS_FAILED

        c = Collector()
        c.set_command("test")

        # Create a feature with a scenario in a non-failed-but-error status
        feature = Feature(
            id="f1",
            name="F1",
            status=STATUS_PASSED,
            duration=0.1,
            scenarios=[
                Scenario(
                    id="sc1",
                    name="S1",
                    feature_id="f1",
                    status=status,
                    duration=0.1,
                    steps=[Step(id="s1", keyword="Given", text="x", status=status, duration=0.1)],
                ),
            ],
        )
        c._features.append(feature)
        report = c.finalize()
        assert report.execution.status == STATUS_FAILED


# ---------------------------------------------------------------------------
# Bug 15: exclude_passed_scenarios with rule scenarios (behavior verification)
# ---------------------------------------------------------------------------


class TestExcludePassedScenariosWithRuleScenarios:
    def test_feature_with_failed_rule_scenario_not_dropped(self):
        """When exclude_passed_scenarios is True, a feature that has
        only passed top-level scenarios but a failed rule scenario
        must NOT be dropped — the failed rule scenario should keep
        the feature in the output.
        """
        from behave_modern_json_report.serializer import Serializer, SerializerOptions
        from behave_modern_json_report.utils import STATUS_FAILED, STATUS_PASSED

        passed_step = Step(
            id="s1",
            keyword="Given",
            text="pass",
            status=STATUS_PASSED,
            duration=0.1,
        )
        failed_step = Step(
            id="s2",
            keyword="When",
            text="fail",
            status=STATUS_FAILED,
            duration=0.1,
        )
        top_scenario = Scenario(
            id="sc1",
            name="Top",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        rule_scenario = Scenario(
            id="sc2",
            name="Rule scenario",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.1,
            steps=[failed_step],
        )
        rule = Rule(
            id="r1",
            name="Rule 1",
            feature_id="f1",
            status=STATUS_FAILED,
            duration=0.1,
            scenarios=[rule_scenario],
        )
        feature = Feature(
            id="f1",
            name="Feature 1",
            status=STATUS_FAILED,
            duration=0.2,
            scenarios=[top_scenario, rule_scenario],
            rules=[rule],
        )
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e1", status=STATUS_FAILED),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )

        opts = SerializerOptions(exclude_passed_scenarios=True)
        data = Serializer(opts).to_dict(report)

        # Feature must still be present
        assert len(data["features"]) == 1
        # Top-level passed scenario must be excluded, but failed rule
        # scenario remains in feature.scenarios (collector adds rule
        # scenarios to both feature.scenarios and rule.scenarios)
        feat = data["features"][0]
        assert len(feat["scenarios"]) == 1
        assert feat["scenarios"][0]["status"] == STATUS_FAILED
        # Rule with failed scenario must also be present
        assert len(feat["rules"]) == 1
        assert len(feat["rules"][0]["scenarios"]) == 1
        assert feat["rules"][0]["scenarios"][0]["status"] == STATUS_FAILED

    def test_feature_with_all_passed_dropped(self):
        """When all scenarios (top-level and rule) are passed,
        the feature should be dropped."""
        from behave_modern_json_report.serializer import Serializer, SerializerOptions
        from behave_modern_json_report.utils import STATUS_PASSED

        passed_step = Step(
            id="s1",
            keyword="Given",
            text="pass",
            status=STATUS_PASSED,
            duration=0.1,
        )
        top_scenario = Scenario(
            id="sc1",
            name="Top",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        rule_scenario = Scenario(
            id="sc2",
            name="Rule scenario",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            steps=[passed_step],
        )
        rule = Rule(
            id="r1",
            name="Rule 1",
            feature_id="f1",
            status=STATUS_PASSED,
            duration=0.1,
            scenarios=[rule_scenario],
        )
        feature = Feature(
            id="f1",
            name="Feature 1",
            status=STATUS_PASSED,
            duration=0.2,
            scenarios=[top_scenario, rule_scenario],
            rules=[rule],
        )
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e1", status=STATUS_PASSED),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )

        opts = SerializerOptions(exclude_passed_scenarios=True)
        data = Serializer(opts).to_dict(report)

        # Feature must be dropped — all scenarios were passed
        assert len(data["features"]) == 0
