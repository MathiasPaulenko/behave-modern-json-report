"""Serialization tests — model to JSON dict and back."""

from __future__ import annotations

import json

from behave_modern_json_report.models import (
    Attachment,
    Background,
    DataTable,
    DataTableRow,
    DocString,
    Error,
    Location,
    StepLog,
)
from behave_modern_json_report.serializer import Serializer, SerializerOptions


class TestSerializerBasic:
    def test_root_keys_present(self, minimal_report):
        data = Serializer().to_dict(minimal_report)
        assert data["schemaVersion"] == minimal_report.schema_version
        assert "execution" in data
        assert "statistics" in data
        assert "environment" in data
        assert "features" in data
        assert "metadata" in data

    def test_json_roundtrip(self, minimal_report):
        text = Serializer().to_json(minimal_report)
        data = json.loads(text)
        assert data["schemaVersion"] == minimal_report.schema_version

    def test_compact_mode(self, minimal_report):
        opts = SerializerOptions(pretty=False)
        text = Serializer(opts).to_json(minimal_report)
        assert "\n" not in text


class TestSerializerOptions:
    def test_exclude_environment(self, minimal_report):
        opts = SerializerOptions(include_environment=False)
        data = Serializer(opts).to_dict(minimal_report)
        assert "environment" not in data

    def test_exclude_passed_scenarios(self, minimal_report):
        opts = SerializerOptions(exclude_passed_scenarios=True)
        data = Serializer(opts).to_dict(minimal_report)
        assert data["features"] == []

    def test_include_attachments_false(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.attachments.append(
            Attachment(
                id="att-1",
                name="screenshot",
                mime_type="image/png",
                encoding="base64",
                content="iVBORw0KGgo=",
            )
        )
        opts = SerializerOptions(include_attachments=False)
        data = Serializer(opts).to_dict(minimal_report)
        step_data = data["features"][0]["scenarios"][0]["steps"][0]
        assert "attachments" not in step_data

    def test_embed_attachments_false_keeps_external(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.attachments.append(
            Attachment(
                id="att-1",
                name="screenshot",
                mime_type="image/png",
                encoding="base64",
                content="iVBORw0KGgo=",
                path="/tmp/screenshot.png",
            )
        )
        opts = SerializerOptions(embed_attachments=False)
        data = Serializer(opts).to_dict(minimal_report)
        att = data["features"][0]["scenarios"][0]["steps"][0]["attachments"][0]
        assert "content" not in att
        assert att["path"] == "/tmp/screenshot.png"


class TestSerializerComplexFields:
    def test_doc_string(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.doc_string = DocString(content="hello", content_type="text/plain")
        data = Serializer().to_dict(minimal_report)
        ds = data["features"][0]["scenarios"][0]["steps"][0]["docString"]
        assert ds["content"] == "hello"
        assert ds["contentType"] == "text/plain"

    def test_data_table(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.data_table = DataTable(
            headers=["a", "b"],
            rows=[DataTableRow(cells=["1", "2"]), DataTableRow(cells=["3", "4"])],
        )
        data = Serializer().to_dict(minimal_report)
        dt = data["features"][0]["scenarios"][0]["steps"][0]["dataTable"]
        assert dt["headers"] == ["a", "b"]
        assert len(dt["rows"]) == 2

    def test_error(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.error = Error(
            id="err-1",
            type="AssertionError",
            message="expected 12 got 11",
            traceback="traceback here",
            location=Location(filename="test.feature", line=5),
        )
        data = Serializer().to_dict(minimal_report)
        err = data["features"][0]["scenarios"][0]["steps"][0]["error"]
        assert err["type"] == "AssertionError"
        assert err["message"] == "expected 12 got 11"
        assert err["traceback"] == "traceback here"

    def test_logs(self, minimal_report):
        step = minimal_report.features[0].scenarios[0].steps[0]
        step.logs.append(StepLog(timestamp="2026-06-30T14:20:00.000Z", level="INFO", message="hi"))
        data = Serializer().to_dict(minimal_report)
        log = data["features"][0]["scenarios"][0]["steps"][0]["logs"][0]
        assert log["level"] == "INFO"
        assert log["message"] == "hi"


class TestSerializerBackground:
    def test_feature_background(self, minimal_report):
        bg = Background(
            id="bg-1",
            name="Common setup",
            keyword="Background",
            location=Location(filename="test.feature", line=2),
        )
        minimal_report.features[0].background = bg
        data = Serializer().to_dict(minimal_report)
        bg_data = data["features"][0]["background"]
        assert bg_data["id"] == "bg-1"
        assert bg_data["name"] == "Common setup"
        assert bg_data["keyword"] == "Background"

    def test_scenario_background(self, minimal_report):
        bg = Background(id="bg-2", name="Shared steps")
        minimal_report.features[0].scenarios[0].background = bg
        data = Serializer().to_dict(minimal_report)
        bg_data = data["features"][0]["scenarios"][0]["background"]
        assert bg_data["id"] == "bg-2"


class TestSerializerNewScenarioFields:
    def test_rule_field(self, minimal_report):
        minimal_report.features[0].scenarios[0].rule = "My Rule"
        data = Serializer().to_dict(minimal_report)
        assert data["features"][0]["scenarios"][0]["rule"] == "My Rule"

    def test_is_outline_field(self, minimal_report):
        minimal_report.features[0].scenarios[0].is_outline = True
        minimal_report.features[0].scenarios[0].outline_name = "Add numbers"
        data = Serializer().to_dict(minimal_report)
        assert data["features"][0]["scenarios"][0]["isOutline"] is True
        assert data["features"][0]["scenarios"][0]["outlineName"] == "Add numbers"


class TestSerializerExtendedStats:
    def test_extended_stats_fields(self, minimal_report):
        minimal_report.statistics.error_count = 2
        minimal_report.statistics.total_attachments = 5
        minimal_report.statistics.total_logs = 3
        minimal_report.statistics.slowest_step_duration = 0.5
        minimal_report.statistics.avg_scenario_duration = 0.3
        minimal_report.statistics.common_exception_type = "ValueError"
        data = Serializer().to_dict(minimal_report)
        stats = data["statistics"]
        assert stats["errorCount"] == 2
        assert stats["totalAttachments"] == 5
        assert stats["totalLogs"] == 3
        assert stats["slowestStepDuration"] == 0.5
        assert stats["avgScenarioDuration"] == 0.3
        assert stats["commonExceptionType"] == "ValueError"


class TestSerializerExtendedEnvironment:
    def test_extended_env_fields(self, minimal_report):
        minimal_report.environment.cwd = "/home/user/project"
        minimal_report.environment.command = "behave"
        minimal_report.environment.user = "tester"
        minimal_report.environment.cpu_count = 8
        minimal_report.environment.memory_mb = 16384
        minimal_report.environment.git_branch = "main"
        minimal_report.environment.git_commit = "abc1234"
        minimal_report.environment.git_remote = "origin"
        data = Serializer().to_dict(minimal_report)
        env = data["environment"]
        assert env["cwd"] == "/home/user/project"
        assert env["command"] == "behave"
        assert env["user"] == "tester"
        assert env["cpuCount"] == 8
        assert env["memoryMb"] == 16384
        assert env["gitBranch"] == "main"
        assert env["gitCommit"] == "abc1234"
        assert env["gitRemote"] == "origin"
