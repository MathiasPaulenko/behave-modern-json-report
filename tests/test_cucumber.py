"""Tests for the Cucumber JSON serializer and formatter."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

from behave_modern_json_report.cucumber_serializer import (
    CucumberSerializerOptions,
    serialize_cucumber,
)
from behave_modern_json_report.models import (
    Attachment,
    Background,
    DataTable,
    DataTableRow,
    DocString,
    Error,
    ExecutionReport,
    Location,
    Step,
    StepLog,
)
from behave_modern_json_report.utils import STATUS_FAILED, STATUS_PASSED

# ---------------------------------------------------------------------------
# Serializer tests
# ---------------------------------------------------------------------------


class TestCucumberSerializer:
    """Unit tests for the Cucumber JSON serializer."""

    def test_minimal_report_produces_array(self, minimal_report: ExecutionReport):
        """Output should be a JSON array of features."""
        data = json.loads(serialize_cucumber(minimal_report))
        assert isinstance(data, list)
        assert len(data) == 1

    def test_feature_structure(self, minimal_report: ExecutionReport):
        """Feature should have required Cucumber fields."""
        data = json.loads(serialize_cucumber(minimal_report))
        feature = data[0]
        assert feature["uri"] == ""
        assert feature["keyword"] == "Feature"
        assert feature["name"] == "Minimal feature"
        assert feature["id"] == "feature-1"
        assert "elements" in feature
        assert isinstance(feature["elements"], list)

    def test_element_structure(self, minimal_report: ExecutionReport):
        """Scenario should be an element with type='scenario'."""
        data = json.loads(serialize_cucumber(minimal_report))
        element = data[0]["elements"][0]
        assert element["type"] == "scenario"
        assert element["keyword"] == "Scenario"
        assert element["name"] == "Minimal scenario"
        assert "steps" in element
        assert isinstance(element["steps"], list)

    def test_step_structure(self, minimal_report: ExecutionReport):
        """Step should have keyword, name, line, match, result."""
        data = json.loads(serialize_cucumber(minimal_report))
        step = data[0]["elements"][0]["steps"][0]
        assert step["keyword"] == "Given"
        assert step["name"] == "a passing step"
        assert step["line"] == 3
        assert "match" in step
        assert "result" in step
        assert step["result"]["status"] == "passed"

    def test_step_match_location(self, minimal_report: ExecutionReport):
        """Step match should include location."""
        data = json.loads(serialize_cucumber(minimal_report))
        step = data[0]["elements"][0]["steps"][0]
        assert step["match"]["location"] == "features/test.feature:3"
        assert step["match"]["arguments"] == []

    def test_duration_in_nanos(self, minimal_report: ExecutionReport):
        """Duration should be in nanoseconds by default."""
        data = json.loads(serialize_cucumber(minimal_report))
        step = data[0]["elements"][0]["steps"][0]
        assert step["result"]["duration"] == 100_000_000  # 0.1s in nanos

    def test_duration_in_seconds(self, minimal_report: ExecutionReport):
        """Duration should be in seconds when duration_in_nanos=False."""
        opts = CucumberSerializerOptions(duration_in_nanos=False)
        data = json.loads(serialize_cucumber(minimal_report, opts))
        step = data[0]["elements"][0]["steps"][0]
        assert step["result"]["duration"] == 0  # int(0.1) = 0

    def test_failed_step_error_message(self):
        """Failed steps should include error_message in result."""
        step = Step(
            id="step-1",
            keyword="When",
            text="something fails",
            status=STATUS_FAILED,
            duration=0.5,
            location=Location(filename="features/test.feature", line=5),
            error=Error(
                id="err-1",
                type="AssertionError",
                message="expected 5 but got 3",
                traceback="Traceback...",
            ),
        )
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        scenario = Scenario(id="scn-1", name="Failing", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        result = data[0]["elements"][0]["steps"][0]["result"]
        assert result["status"] == "failed"
        assert "AssertionError" in result["error_message"]
        assert "expected 5 but got 3" in result["error_message"]

    def test_status_mapping(self):
        """All statuses should map to valid Cucumber statuses."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        statuses = [
            ("passed", "passed"),
            ("failed", "failed"),
            ("skipped", "skipped"),
            ("undefined", "undefined"),
            ("pending", "pending"),
            ("untested", "skipped"),
            ("error", "failed"),
            ("hook_error", "failed"),
            ("cleanup_error", "failed"),
            ("xfailed", "skipped"),
            ("xpassed", "passed"),
        ]
        for our_status, expected in statuses:
            step = Step(
                id=f"step-{our_status}",
                keyword="Given",
                text=f"step {our_status}",
                status=our_status,
                location=Location(filename="f.feature", line=1),
            )
            scenario = Scenario(
                id=f"scn-{our_status}",
                name=f"Scenario {our_status}",
                feature_id="feat-1",
                steps=[step],
            )
            feature = Feature(id="feat-1", name="F", scenarios=[scenario])
            report = ExecutionReport(
                schema_version=SCHEMA_VERSION,
                execution=Execution(execution_id="exec-1"),
                statistics=Statistics(),
                environment=Environment(),
                features=[feature],
                metadata=Metadata(),
            )
            data = json.loads(serialize_cucumber(report))
            result = data[0]["elements"][0]["steps"][0]["result"]
            assert result["status"] == expected, f"{our_status} should map to {expected}"

    def test_doc_string(self):
        """DocString should be converted to doc_string object."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="a step with doc string",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            doc_string=DocString(
                content="line1\nline2",
                content_type="text/plain",
                line=2,
            ),
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        step_data = data[0]["elements"][0]["steps"][0]
        assert "doc_string" in step_data
        assert step_data["doc_string"]["value"] == "line1\nline2"
        assert step_data["doc_string"]["content_type"] == "text/plain"

    def test_data_table(self):
        """DataTable should be converted to rows array."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="a step with table",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            data_table=DataTable(
                rows=[
                    DataTableRow(cells=["a", "b"]),
                    DataTableRow(cells=["c", "d"]),
                ]
            ),
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        step_data = data[0]["elements"][0]["steps"][0]
        assert "rows" in step_data
        assert step_data["rows"][0]["cells"] == ["a", "b"]
        assert step_data["rows"][1]["cells"] == ["c", "d"]

    def test_attachments_as_embeddings(self):
        """Attachments should be converted to embeddings with base64 data."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="a step with attachment",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            attachments=[
                Attachment(
                    id="att-1",
                    name="screenshot.png",
                    mime_type="image/png",
                    encoding="base64",
                    content="iVBORw0KGgo=",
                ),
            ],
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        step_data = data[0]["elements"][0]["steps"][0]
        assert "embeddings" in step_data
        assert step_data["embeddings"][0]["mime_type"] == "image/png"
        assert step_data["embeddings"][0]["data"] == "iVBORw0KGgo="
        assert step_data["embeddings"][0]["name"] == "screenshot.png"

    def test_logs_as_output(self):
        """Step logs should be converted to output array."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="a step with logs",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            logs=[
                StepLog(timestamp="2026-01-01T00:00:00Z", level="INFO", message="hello"),
                StepLog(timestamp="2026-01-01T00:00:01Z", level="ERROR", message="oops"),
            ],
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        step_data = data[0]["elements"][0]["steps"][0]
        assert "output" in step_data
        assert "[INFO] hello" in step_data["output"]
        assert "[ERROR] oops" in step_data["output"]

    def test_background_as_element(self):
        """Background should appear as first element with type='background'."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        bg_step = Step(
            id="bg-step-1",
            keyword="Given",
            text="background step",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=2),
        )
        bg = Background(
            id="bg-1",
            name="",
            keyword="Background",
            location=Location(filename="f.feature", line=1),
            steps=[bg_step],
        )
        scenario = Scenario(
            id="scn-1",
            name="S",
            feature_id="feat-1",
            steps=[
                Step(
                    id="step-1",
                    keyword="When",
                    text="do something",
                    status=STATUS_PASSED,
                    location=Location(filename="f.feature", line=5),
                )
            ],
        )
        feature = Feature(id="feat-1", name="F", scenarios=[scenario], background=bg)
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        elements = data[0]["elements"]
        assert len(elements) == 2
        assert elements[0]["type"] == "background"
        assert elements[0]["keyword"] == "Background"
        assert elements[1]["type"] == "scenario"

    def test_tags_conversion(self):
        """Tags should be converted to Cucumber tag objects."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        scenario = Scenario(
            id="scn-1",
            name="S",
            feature_id="feat-1",
            tags=["smoke", "regression"],
            steps=[
                Step(
                    id="step-1",
                    keyword="Given",
                    text="x",
                    status=STATUS_PASSED,
                    location=Location(filename="f.feature", line=1),
                )
            ],
        )
        feature = Feature(id="feat-1", name="F", tags=["feature-tag"], scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        assert data[0]["tags"] == [{"name": "feature-tag"}]
        assert data[0]["elements"][0]["tags"] == [
            {"name": "smoke"},
            {"name": "regression"},
        ]

    def test_pretty_vs_compact(self, minimal_report: ExecutionReport):
        """Pretty output should have indentation, compact should not."""
        pretty = serialize_cucumber(minimal_report, CucumberSerializerOptions(pretty=True))
        compact = serialize_cucumber(minimal_report, CucumberSerializerOptions(pretty=False))
        assert "  " in pretty  # has indentation
        assert "\n" not in compact  # no newlines in compact

    def test_exclude_attachments(self):
        """When embed_attachments=False, no embeddings should appear."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="x",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            attachments=[
                Attachment(
                    id="att-1",
                    name="img.png",
                    mime_type="image/png",
                    encoding="base64",
                    content="abc",
                )
            ],
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        opts = CucumberSerializerOptions(embed_attachments=False)
        data = json.loads(serialize_cucumber(report, opts))
        assert "embeddings" not in data[0]["elements"][0]["steps"][0]

    def test_exclude_output(self):
        """When include_output=False, no output should appear."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        step = Step(
            id="step-1",
            keyword="Given",
            text="x",
            status=STATUS_PASSED,
            location=Location(filename="f.feature", line=1),
            logs=[
                StepLog(timestamp="t", level="INFO", message="hi"),
            ],
        )
        scenario = Scenario(id="scn-1", name="S", feature_id="feat-1", steps=[step])
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        opts = CucumberSerializerOptions(include_output=False)
        data = json.loads(serialize_cucumber(report, opts))
        assert "output" not in data[0]["elements"][0]["steps"][0]

    def test_scenario_outline_keyword(self):
        """Scenario outline should have keyword='Scenario Outline'."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Scenario,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        scenario = Scenario(
            id="scn-1",
            name="Outline example",
            feature_id="feat-1",
            is_outline=True,
            outline_name="Add multiple numbers -- @1.1",
            steps=[
                Step(
                    id="step-1",
                    keyword="Given",
                    text="x",
                    status=STATUS_PASSED,
                    location=Location(filename="f.feature", line=1),
                )
            ],
        )
        feature = Feature(id="feat-1", name="F", scenarios=[scenario])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        element = data[0]["elements"][0]
        assert element["keyword"] == "Scenario Outline"
        assert element["name"] == "Add multiple numbers -- @1.1"

    def test_multiple_features(self):
        """Multiple features should produce multiple array entries."""
        from behave_modern_json_report.models import (
            Environment,
            Execution,
            ExecutionReport,
            Feature,
            Metadata,
            Statistics,
        )
        from behave_modern_json_report.schema import SCHEMA_VERSION

        f1 = Feature(id="f1", name="Feature 1", scenarios=[])
        f2 = Feature(id="f2", name="Feature 2", scenarios=[])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="exec-1"),
            statistics=Statistics(),
            environment=Environment(),
            features=[f1, f2],
            metadata=Metadata(),
        )
        data = json.loads(serialize_cucumber(report))
        assert len(data) == 2
        assert data[0]["name"] == "Feature 1"
        assert data[1]["name"] == "Feature 2"


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestCucumberFormatter:
    """Unit tests for the CucumberJSONFormatter."""

    def test_formatter_writes_json_array(self):
        """Formatter should write a valid JSON array to the stream."""
        from behave_modern_json_report.cucumber_formatter import (
            CucumberJSONFormatter,
        )

        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream)

        # Simulate a minimal behave run
        feature = SimpleNamespace(
            name="Test Feature",
            tags=[],
            filename="features/test.feature",
            line=1,
            description=None,
        )
        scenario = SimpleNamespace(
            name="Test Scenario",
            tags=[],
            filename="features/test.feature",
            line=3,
            description=None,
            examples=None,
            effective_tags=[],
        )
        step = SimpleNamespace(
            name="a step",
            keyword="Given",
            status="passed",
            duration=0.1,
            filename="features/test.feature",
            line=4,
            error_message=None,
            text="",
        )

        fmt.feature(feature)
        fmt.scenario(scenario)
        fmt.step(step)
        fmt.result(step)
        fmt.eof()

        output = stream.getvalue()
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Test Feature"
        assert data[0]["elements"][0]["name"] == "Test Scenario"
        assert data[0]["elements"][0]["steps"][0]["result"]["status"] == "passed"

    def test_formatter_name_and_description(self):
        """Formatter should have correct name and description."""
        from behave_modern_json_report.cucumber_formatter import (
            CucumberJSONFormatter,
        )

        assert CucumberJSONFormatter.name == "cucumber-json"
        assert "Cucumber" in CucumberJSONFormatter.description
