"""Regression tests for the Collector."""

from __future__ import annotations

from types import SimpleNamespace

from behave_modern_json_report.collector import Collector
from behave_modern_json_report.serializer import Serializer
from behave_modern_json_report.utils import STATUS_FAILED, STATUS_PASSED
from behave_modern_json_report.validator import validate_report


def _behave_feature(name="Feature 1", tags=None, filename="f.feature", line=1):
    return SimpleNamespace(
        name=name,
        tags=tags or [],
        filename=filename,
        line=line,
        description=None,
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


class TestCollectorLifecycle:
    def test_full_passing_run(self):
        c = Collector(project_name="test")
        f = _behave_feature()
        c.start_feature(f)
        sc = _behave_scenario()
        c.start_scenario(sc)
        step = _behave_step()
        c.start_step(step)
        c.end_step(step)
        c.end_scenario(sc)
        c.end_feature(f)
        report = c.finalize()

        assert report.execution.status == STATUS_PASSED
        assert len(report.features) == 1
        assert len(report.features[0].scenarios) == 1
        assert len(report.features[0].scenarios[0].steps) == 1
        assert report.statistics.passed == 1
        assert report.statistics.failed == 0

    def test_failed_step_propagates(self):
        c = Collector()
        c.start_feature(_behave_feature())
        c.start_scenario(_behave_scenario())
        c.start_step(_behave_step())
        c.end_step(_behave_step(status="failed"))
        c.end_scenario(_behave_scenario())
        c.end_feature(_behave_feature())
        report = c.finalize()

        assert report.execution.status == STATUS_FAILED
        assert report.statistics.failed == 1
        assert report.features[0].status == STATUS_FAILED
        assert report.features[0].scenarios[0].status == STATUS_FAILED

    def test_report_validates(self):
        c = Collector(project_name="test", metadata={"branch": "main"})
        c.start_feature(_behave_feature(tags=["@smoke"]))
        c.start_scenario(_behave_scenario(tags=["@fast"]))
        c.start_step(_behave_step())
        c.end_step(_behave_step())
        c.end_scenario(_behave_scenario())
        c.end_feature(_behave_feature())
        report = c.finalize()

        result = validate_report(report)
        assert result.valid, [str(e) for e in result.errors]

    def test_metadata_preserved(self):
        c = Collector(metadata={"browser": "Chrome", "environment": "QA"})
        c.start_feature(_behave_feature())
        c.start_scenario(_behave_scenario())
        c.start_step(_behave_step())
        c.end_step(_behave_step())
        c.end_scenario(_behave_scenario())
        c.end_feature(_behave_feature())
        report = c.finalize()

        assert report.metadata.data["browser"] == "Chrome"
        assert report.metadata.data["environment"] == "QA"

    def test_serialized_report_validates(self):
        c = Collector()
        c.start_feature(_behave_feature())
        c.start_scenario(_behave_scenario())
        c.start_step(_behave_step())
        c.end_step(_behave_step())
        c.end_scenario(_behave_scenario())
        c.end_feature(_behave_feature())
        report = c.finalize()

        data = Serializer().to_dict(report)
        assert data["schemaVersion"] == report.schema_version
        assert data["execution"]["executionId"] == report.execution.execution_id
        assert data["features"][0]["scenarios"][0]["steps"][0]["status"] == STATUS_PASSED
