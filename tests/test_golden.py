"""Golden JSON tests — structural stability of the serialized output."""

from __future__ import annotations

from behave_modern_json_report.schema import SCHEMA_VERSION
from behave_modern_json_report.validator import validate_dict


class TestGoldenStructure:
    def test_golden_has_required_root_keys(self, golden_report_dict):
        for key in ("schemaVersion", "execution", "statistics", "features", "metadata"):
            assert key in golden_report_dict, f"missing root key: {key}"

    def test_golden_schema_version(self, golden_report_dict):
        assert golden_report_dict["schemaVersion"] == SCHEMA_VERSION

    def test_golden_execution_fields(self, golden_report_dict):
        exc = golden_report_dict["execution"]
        for key in ("executionId", "status", "duration"):
            assert key in exc

    def test_golden_statistics_fields(self, golden_report_dict):
        stats = golden_report_dict["statistics"]
        for key in (
            "features",
            "scenarios",
            "steps",
            "passed",
            "failed",
            "skipped",
            "undefined",
            "pending",
            "passRate",
            "duration",
        ):
            assert key in stats

    def test_golden_feature_fields(self, golden_report_dict):
        feature = golden_report_dict["features"][0]
        for key in ("id", "name", "status", "duration", "scenarios"):
            assert key in feature

    def test_golden_scenario_fields(self, golden_report_dict):
        scenario = golden_report_dict["features"][0]["scenarios"][0]
        for key in ("id", "name", "featureId", "status", "duration", "steps"):
            assert key in scenario

    def test_golden_step_fields(self, golden_report_dict):
        step = golden_report_dict["features"][0]["scenarios"][0]["steps"][0]
        for key in ("id", "keyword", "text", "status", "duration"):
            assert key in step

    def test_golden_validates(self, golden_report_dict):
        result = validate_dict(golden_report_dict)
        assert result.valid, [str(e) for e in result.errors]


class TestGoldenCounts:
    def test_feature_count(self, golden_report_dict):
        assert len(golden_report_dict["features"]) == 1

    def test_scenario_count(self, golden_report_dict):
        assert len(golden_report_dict["features"][0]["scenarios"]) == 3

    def test_step_count(self, golden_report_dict):
        total = sum(
            len(sc["steps"]) for f in golden_report_dict["features"] for sc in f["scenarios"]
        )
        assert total == 12

    def test_all_passed(self, golden_report_dict):
        stats = golden_report_dict["statistics"]
        assert stats["passed"] == 12
        assert stats["failed"] == 0
        assert stats["passRate"] == 1.0
