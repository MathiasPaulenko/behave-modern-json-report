"""Regression tests for the Formatter."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

from behave_modern_json_report.formatter import ModernJSONFormatter
from behave_modern_json_report.serializer import SerializerOptions
from behave_modern_json_report.validator import validate_json


def _feature():
    return SimpleNamespace(name="F", tags=[], filename="f.feature", line=1, description=None)


def _scenario():
    return SimpleNamespace(
        name="S", tags=[], filename="f.feature", line=3, description=None, examples=None
    )


def _step(status="passed"):
    return SimpleNamespace(
        keyword="Given",
        name="step",
        status=status,
        filename="f.feature",
        line=5,
        error=None,
        doc_string=None,
        table=None,
    )


class TestFormatter:
    def test_writes_valid_json_to_stream(self):
        stream = io.StringIO()
        fmt = ModernJSONFormatter(stream=stream, options=SerializerOptions(pretty=False))
        fmt.feature(_feature())
        fmt.scenario(_scenario())
        fmt.step(_step())
        fmt.result(_step())
        fmt.scenario_result(_scenario())
        fmt.feature_result(_feature())
        fmt.eof()

        output = stream.getvalue().strip()
        assert output
        result = validate_json(output)
        assert result.valid, [str(e) for e in result.errors]

    def test_metadata_appears_in_output(self):
        stream = io.StringIO()
        fmt = ModernJSONFormatter(
            stream=stream,
            options=SerializerOptions(pretty=False),
            project_name="demo",
            metadata={"branch": "dev"},
        )
        fmt.feature(_feature())
        fmt.scenario(_scenario())
        fmt.step(_step())
        fmt.result(_step())
        fmt.scenario_result(_scenario())
        fmt.feature_result(_feature())
        fmt.eof()

        data = json.loads(stream.getvalue())
        assert data["execution"]["projectName"] == "demo"
        assert data["metadata"]["branch"] == "dev"

    def test_double_eof_does_not_double_write(self):
        stream = io.StringIO()
        fmt = ModernJSONFormatter(stream=stream, options=SerializerOptions(pretty=False))
        fmt.feature(_feature())
        fmt.scenario(_scenario())
        fmt.step(_step())
        fmt.result(_step())
        fmt.scenario_result(_scenario())
        fmt.feature_result(_feature())
        fmt.eof()
        fmt.eof()  # should be a no-op
        fmt.close()  # should be a no-op

        lines = [line for line in stream.getvalue().splitlines() if line.strip()]
        assert len(lines) == 1
