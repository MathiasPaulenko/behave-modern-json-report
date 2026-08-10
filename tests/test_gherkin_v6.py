"""Tests for Gherkin v6 features: Rule keyword, rule backgrounds, example tags,
scenario outlines with examples, and the 'Example' keyword.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from behave_modern_json_report.collector import Collector
from behave_modern_json_report.cucumber_serializer import (
    serialize_cucumber,
)
from behave_modern_json_report.models import (
    Background,
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
from behave_modern_json_report.serializer import Serializer
from behave_modern_json_report.utils import STATUS_PASSED


def _make_step(
    name: str = "a step",
    keyword: str = "Given",
    status: str = STATUS_PASSED,
    line: int = 5,
) -> Step:
    return Step(
        id=f"step-{name}",
        keyword=keyword,
        text=name,
        status=status,
        duration=0.1,
        location=Location(filename="features/test.feature", line=line),
    )


def _make_report_with_rules() -> ExecutionReport:
    """Build a report with a feature containing a rule with background and scenarios."""
    bg_step = _make_step("rule background step", line=4)
    rule_bg = Background(
        id="bg-rule-1",
        name="Rule setup",
        keyword="Background",
        location=Location(filename="features/test.feature", line=3),
        steps=[bg_step],
    )
    scenario1 = Scenario(
        id="scn-1",
        name="Scenario inside rule",
        feature_id="feat-1",
        tags=["smoke"],
        steps=[_make_step("do something", line=8)],
        rule="My Rule",
        rule_id="rule-1",
        background=rule_bg,
    )
    scenario2 = Scenario(
        id="scn-2",
        name="Outline example inside rule",
        feature_id="feat-1",
        tags=["regression"],
        steps=[_make_step("check value", line=15)],
        rule="My Rule",
        rule_id="rule-1",
        is_outline=True,
        outline_name="Outline example -- @1.1",
        example_tags=["@fast"],
        examples=[{"col1": "val1"}],
        background=rule_bg,
    )
    rule = Rule(
        id="rule-1",
        name="My Rule",
        feature_id="feat-1",
        description="A rule description",
        tags=["rule-tag"],
        location=Location(filename="features/test.feature", line=2),
        background=rule_bg,
        scenarios=[scenario1, scenario2],
        status=STATUS_PASSED,
        duration=0.2,
    )
    feature = Feature(
        id="feat-1",
        name="Feature with rules",
        status=STATUS_PASSED,
        duration=0.3,
        scenarios=[scenario1, scenario2],
        rules=[rule],
    )
    return ExecutionReport(
        schema_version=SCHEMA_VERSION,
        execution=Execution(execution_id="exec-1"),
        statistics=Statistics(),
        environment=Environment(),
        features=[feature],
        metadata=Metadata(),
    )


class TestRuleModel:
    """Tests for the Rule dataclass."""

    def test_rule_exists(self):
        rule = Rule(id="r1", name="My Rule", feature_id="f1")
        assert rule.name == "My Rule"
        assert rule.feature_id == "f1"
        assert rule.scenarios == []
        assert rule.background is None
        assert rule.tags == []
        assert rule.status == STATUS_PASSED

    def test_rule_with_background(self):
        bg = Background(id="bg-1", name="Setup")
        rule = Rule(id="r1", name="My Rule", feature_id="f1", background=bg)
        assert rule.background is not None
        assert rule.background.id == "bg-1"

    def test_rule_exported_from_package(self):
        from behave_modern_json_report import Rule as ExportedRule

        assert ExportedRule is Rule


class TestSerializerRules:
    """Tests for rule serialization in the modern JSON format."""

    def test_feature_has_rules_array(self):
        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        feature = data["features"][0]
        assert "rules" in feature
        assert len(feature["rules"]) == 1

    def test_rule_structure(self):
        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        rule = data["features"][0]["rules"][0]
        assert rule["id"] == "rule-1"
        assert rule["name"] == "My Rule"
        assert rule["featureId"] == "feat-1"
        assert rule["description"] == "A rule description"
        assert rule["tags"] == ["rule-tag"]
        assert rule["status"] == "passed"
        assert "scenarios" in rule
        assert len(rule["scenarios"]) == 2

    def test_rule_background_serialized(self):
        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        rule = data["features"][0]["rules"][0]
        assert "background" in rule
        assert rule["background"]["id"] == "bg-rule-1"
        assert rule["background"]["name"] == "Rule setup"

    def test_scenario_has_rule_id(self):
        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        scenario = data["features"][0]["scenarios"][0]
        assert scenario["rule"] == "My Rule"
        assert scenario["ruleId"] == "rule-1"

    def test_scenario_has_example_tags(self):
        report = _make_report_with_rules()
        data = Serializer().to_dict(report)
        scenario = data["features"][0]["scenarios"][1]
        assert scenario["exampleTags"] == ["@fast"]

    def test_feature_without_rules_has_no_rules_key(self):
        from behave_modern_json_report.models import (
            Environment as Ev,
        )
        from behave_modern_json_report.models import (
            Execution as Ex,
        )
        from behave_modern_json_report.models import (
            ExecutionReport as ER,
        )
        from behave_modern_json_report.models import (
            Feature as F,
        )
        from behave_modern_json_report.models import (
            Metadata as M,
        )
        from behave_modern_json_report.models import (
            Scenario as S,
        )
        from behave_modern_json_report.models import (
            Statistics as St,
        )

        scenario = S(id="s1", name="S", feature_id="f1", steps=[_make_step()])
        feature = F(id="f1", name="F", scenarios=[scenario])
        report = ER(
            schema_version=SCHEMA_VERSION,
            execution=Ex(execution_id="e1"),
            statistics=St(),
            environment=Ev(),
            features=[feature],
            metadata=M(),
        )
        data = Serializer().to_dict(report)
        assert "rules" not in data["features"][0]


class TestCucumberSerializerRules:
    """Tests for rule serialization in Cucumber JSON format."""

    def test_rule_scenarios_appear_as_elements(self):
        report = _make_report_with_rules()
        data = json.loads(serialize_cucumber(report))
        elements = data[0]["elements"]
        # 1 rule background + 2 scenarios from the rule
        assert len(elements) == 3
        scenario_elements = [e for e in elements if e["type"] == "scenario"]
        assert len(scenario_elements) == 2
        for el in scenario_elements:
            assert el["rule"] == "My Rule"
            assert el["ruleId"] == "rule-1"

    def test_rule_background_appears_as_element(self):
        report = _make_report_with_rules()
        data = json.loads(serialize_cucumber(report))
        elements = data[0]["elements"]
        # Find the background element (should have rule info)
        bg_elements = [e for e in elements if e["type"] == "background"]
        # The rule background is assigned to scenarios, so it should appear
        # as a background element with rule info
        assert len(bg_elements) >= 1
        bg = bg_elements[0]
        assert bg["rule"] == "My Rule"
        assert bg["ruleId"] == "rule-1"

    def test_example_tags_in_cucumber(self):
        report = _make_report_with_rules()
        data = json.loads(serialize_cucumber(report))
        elements = data[0]["elements"]
        # Find the outline scenario
        outline = [e for e in elements if e.get("keyword") == "Scenario Outline"]
        assert len(outline) == 1
        assert outline[0]["exampleTags"] == ["@fast"]

    def test_no_duplicate_scenarios(self):
        """Scenarios in rules should not be duplicated in feature.scenarios."""
        report = _make_report_with_rules()
        data = json.loads(serialize_cucumber(report))
        elements = data[0]["elements"]
        ids = [e["id"] for e in elements if e["type"] == "scenario"]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs found"


class TestCollectorRules:
    """Tests for the Collector's rule lifecycle methods."""

    def test_start_rule_creates_rule_entity(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="Test Feature",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=["rule-tag"],
            filename="test.feature",
            line=2,
            description=None,
            background=None,
        )
        collector.start_feature(feature)
        result = collector.start_rule(rule)
        assert result is not None
        assert result.name == "My Rule"
        assert result.feature_id == collector._current_feature.id
        assert result.tags == ["rule-tag"]
        assert len(collector._current_feature.rules) == 1

    def test_start_rule_with_background(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        bg = SimpleNamespace(
            name="Rule BG",
            keyword="Background",
            filename="test.feature",
            line=3,
            steps=[
                SimpleNamespace(
                    name="bg step",
                    keyword="Given",
                    status="passed",
                    duration=0.1,
                    filename="test.feature",
                    line=4,
                    error_message=None,
                    text="",
                )
            ],
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=[],
            filename="test.feature",
            line=2,
            description=None,
            background=bg,
        )
        collector.start_feature(feature)
        result = collector.start_rule(rule)
        assert result is not None
        assert result.background is not None
        assert result.background.name == "Rule BG"
        assert len(result.background.steps) == 1

    def test_scenario_inside_rule_gets_rule_id(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=[],
            filename="test.feature",
            line=2,
            description=None,
            background=None,
        )
        scenario = SimpleNamespace(
            name="S in rule",
            tags=[],
            type="scenario",
            filename="test.feature",
            line=5,
            description=None,
            examples=None,
            effective_tags=[],
        )
        collector.start_feature(feature)
        collector.start_rule(rule)
        sc = collector.start_scenario(scenario)
        assert sc is not None
        assert sc.rule == "My Rule"
        assert sc.rule_id is not None
        assert sc.rule_id == collector._current_rule.id

    def test_scenario_inside_rule_gets_rule_background(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        bg = SimpleNamespace(
            name="Rule BG",
            keyword="Background",
            filename="test.feature",
            line=3,
            steps=[
                SimpleNamespace(
                    name="bg step",
                    keyword="Given",
                    status="passed",
                    duration=0.1,
                    filename="test.feature",
                    line=4,
                    error_message=None,
                    text="",
                )
            ],
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=[],
            filename="test.feature",
            line=2,
            description=None,
            background=bg,
        )
        scenario = SimpleNamespace(
            name="S in rule",
            tags=[],
            type="scenario",
            filename="test.feature",
            line=6,
            description=None,
            examples=None,
            effective_tags=[],
        )
        collector.start_feature(feature)
        collector.start_rule(rule)
        sc = collector.start_scenario(scenario)
        assert sc is not None
        assert sc.background is not None
        assert sc.background.name == "Rule BG"

    def test_example_keyword_detected_as_outline(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        scenario = SimpleNamespace(
            name="Example row",
            tags=[],
            type="example",
            filename="test.feature",
            line=5,
            description=None,
            examples=None,
            effective_tags=[],
        )
        collector.start_feature(feature)
        sc = collector.start_scenario(scenario)
        assert sc is not None
        assert sc.is_outline is True

    def test_example_tags_extracted(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        scenario = SimpleNamespace(
            name="Outline row",
            tags=["scenario-tag"],
            type="scenario_outline",
            filename="test.feature",
            line=5,
            description=None,
            examples=None,
            effective_tags=["scenario-tag", "@fast", "@smoke"],
        )
        collector.start_feature(feature)
        sc = collector.start_scenario(scenario)
        assert sc is not None
        assert "@fast" in sc.example_tags
        assert "@smoke" in sc.example_tags

    def test_end_rule_finalizes(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=[],
            filename="test.feature",
            line=2,
            description=None,
            background=None,
        )
        collector.start_feature(feature)
        collector.start_rule(rule)
        assert collector._current_rule is not None
        collector.end_rule()
        assert collector._current_rule is None
        assert collector._current_rule_name is None

    def test_end_feature_finalizes_pending_rule(self):
        collector = Collector()
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="test.feature",
            line=1,
            description=None,
            background=None,
        )
        rule = SimpleNamespace(
            name="My Rule",
            tags=[],
            filename="test.feature",
            line=2,
            description=None,
            background=None,
        )
        collector.start_feature(feature)
        collector.start_rule(rule)
        collector.end_feature(None)
        assert collector._current_rule is None


class TestRuleStatus:
    """Tests for rule_status function."""

    def test_rule_status_passed(self):
        from behave_modern_json_report.statistics import rule_status

        rule = Rule(
            id="r1",
            name="R",
            feature_id="f1",
            scenarios=[
                Scenario(id="s1", name="S1", feature_id="f1", status="passed"),
                Scenario(id="s2", name="S2", feature_id="f1", status="passed"),
            ],
        )
        assert rule_status(rule) == "passed"

    def test_rule_status_failed(self):
        from behave_modern_json_report.statistics import rule_status

        rule = Rule(
            id="r1",
            name="R",
            feature_id="f1",
            scenarios=[
                Scenario(id="s1", name="S1", feature_id="f1", status="passed"),
                Scenario(id="s2", name="S2", feature_id="f1", status="failed"),
            ],
        )
        assert rule_status(rule) == "failed"

    def test_rule_status_empty(self):
        from behave_modern_json_report.statistics import rule_status

        rule = Rule(id="r1", name="R", feature_id="f1")
        assert rule_status(rule) == "passed"
