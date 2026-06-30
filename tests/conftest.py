"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from behave_modern_json_report.models import (
    Environment,
    Execution,
    ExecutionReport,
    Feature,
    Location,
    Metadata,
    Scenario,
    Statistics,
    Step,
)
from behave_modern_json_report.schema import SCHEMA_VERSION
from behave_modern_json_report.utils import STATUS_PASSED

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def golden_report_path() -> Path:
    return EXAMPLES / "golden-report.json"


@pytest.fixture
def golden_report_dict(golden_report_path: Path) -> dict:
    return json.loads(golden_report_path.read_text(encoding="utf-8"))


@pytest.fixture
def minimal_report() -> ExecutionReport:
    step = Step(
        id="step-1",
        keyword="Given",
        text="a passing step",
        status=STATUS_PASSED,
        duration=0.1,
        location=Location(filename="features/test.feature", line=3),
    )
    scenario = Scenario(
        id="scenario-1",
        name="Minimal scenario",
        feature_id="feature-1",
        status=STATUS_PASSED,
        duration=0.1,
        steps=[step],
    )
    feature = Feature(
        id="feature-1",
        name="Minimal feature",
        status=STATUS_PASSED,
        duration=0.1,
        scenarios=[scenario],
    )
    execution = Execution(
        execution_id="exec-1",
        project_name="test",
        start_time="2026-06-30T14:20:00.000Z",
        end_time="2026-06-30T14:20:00.100Z",
        duration=0.1,
        status=STATUS_PASSED,
    )
    return ExecutionReport(
        schema_version=SCHEMA_VERSION,
        execution=execution,
        statistics=Statistics(
            features=1,
            scenarios=1,
            steps=1,
            passed=1,
            pass_rate=1.0,
            duration=0.1,
        ),
        environment=Environment(
            python_version="3.12.3",
            behave_version="1.2.6",
            platform="linux",
            os="Linux",
            os_version="6.5.0",
            hostname="test-host",
        ),
        features=[feature],
        metadata=Metadata(data={"branch": "main"}),
    )
