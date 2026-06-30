"""Schema validation tests."""

from __future__ import annotations

from behave_modern_json_report.validator import validate_dict, validate_json, validate_report


class TestValidateGoldenReport:
    def test_golden_report_is_valid(self, golden_report_dict):
        result = validate_dict(golden_report_dict)
        assert result.valid, [str(e) for e in result.errors]

    def test_golden_report_json_string(self, golden_report_path):
        text = golden_report_path.read_text(encoding="utf-8")
        result = validate_json(text)
        assert result.valid, [str(e) for e in result.errors]


class TestValidateModelReport:
    def test_minimal_report_valid(self, minimal_report):
        result = validate_report(minimal_report)
        assert result.valid, [str(e) for e in result.errors]


class TestValidateInvalidReports:
    def test_missing_schema_version(self, golden_report_dict):
        del golden_report_dict["schemaVersion"]
        result = validate_dict(golden_report_dict)
        assert not result.valid
        assert any("schemaVersion" in e.message for e in result.errors)

    def test_missing_execution(self, golden_report_dict):
        del golden_report_dict["execution"]
        result = validate_dict(golden_report_dict)
        assert not result.valid

    def test_wrong_type_pass_rate(self, golden_report_dict):
        golden_report_dict["statistics"]["passRate"] = "high"
        result = validate_dict(golden_report_dict)
        assert not result.valid

    def test_invalid_json_string(self):
        result = validate_json("{not valid json")
        assert not result.valid
        assert any("invalid JSON" in e.message for e in result.errors)

    def test_root_not_object(self):
        result = validate_json("[1, 2, 3]")
        assert not result.valid

    def test_feature_missing_id(self, golden_report_dict):
        del golden_report_dict["features"][0]["id"]
        result = validate_dict(golden_report_dict)
        assert not result.valid
        assert any("'id'" in e.message for e in result.errors)

    def test_step_missing_required_field(self, golden_report_dict):
        step = golden_report_dict["features"][0]["scenarios"][0]["steps"][0]
        del step["keyword"]
        result = validate_dict(golden_report_dict)
        assert not result.valid
        assert any("'keyword'" in e.message for e in result.errors)
