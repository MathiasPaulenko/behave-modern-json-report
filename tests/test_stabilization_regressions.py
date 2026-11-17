"""Regression tests for bugs found during the stabilization bug hunt.

Each test corresponds to a defect verified against real Behave 1.3.3
behaviour or direct API abuse:

1. Formatters lacked ``embedding()`` — ``context.attach()`` data was dropped.
2. ``_find_formatter`` returned only the first compatible formatter — with two
   active formatters the second report lost every attachment/log.
3. ``scenario.background`` ignored Behave's background inheritance — rule
   scenarios lost the feature background steps.
4. ``_feature_to_cucumber`` emitted rule scenarios before top-level ones,
   breaking document order.
5. ``normalize_status`` mapped ``pending_warn`` to ``untested``.
6. ``if duration:`` falsy checks replaced real ``0.0`` durations with a
   monotonic fallback measured since the (upfront) step event.
7. ``os.getcwd()`` crashed when the process cwd had been deleted.
8. NaN/Infinity durations produced invalid JSON (``NaN`` literal).
9. The structural validator accepted ``bool`` as a number and skipped the
   status enum used by the JSON Schema.
10. ``_pending`` items buffered after the last step were silently dropped.
11. External attachments put ``att.path`` into the embedding ``data`` field,
    which consumers read as base64.
12. ``_location`` crashed on a non-numeric ``line`` attribute.
13. ``_find_formatter`` raised ``ReferenceError`` on a dead runner proxy;
    ``attach_screenshot`` crashed on non-bytes payloads.
14. Empty rules survived ``exclude_passed_scenarios`` as noise.
15. ``passRate`` ignored error/undefined/pending steps in the denominator.
16. ``_duration`` produced negative/overflowing nanos for bad inputs.
17. ``compute_statistics`` ignored scenarios that only lived in
    ``rule.scenarios`` (hand-built models).
18. Behave's ``Configuration`` has no ``.get`` — every documented formatter
    option (``pretty``, ``exclude_passed_scenarios``, ...) was dead code.
    Options are now read from ``mjr.*`` userdata keys, the channel behave
    actually exposes.
19. ``environment_extra`` passed straight to ``merge_dicts`` — a string value
    from userdata crashed ``finalize``; JSON strings are now parsed and other
    types ignored.
20. ``Serializer.to_dict(None)`` crashed with ``AttributeError`` and ``None``
    collection fields exploded during iteration; both now fail cleanly.
"""

from __future__ import annotations

import base64
import io
import json
import math
from types import SimpleNamespace

import pytest

from behave_modern_json_report import attach
from behave_modern_json_report.collector import Collector
from behave_modern_json_report.cucumber_formatter import CucumberJSONFormatter
from behave_modern_json_report.cucumber_serializer import serialize_cucumber
from behave_modern_json_report.formatter import ModernJSONFormatter
from behave_modern_json_report.models import (
    Attachment,
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
from behave_modern_json_report.serializer import Serializer, SerializerOptions
from behave_modern_json_report.statistics import compute_statistics, feature_status
from behave_modern_json_report.utils import (
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    normalize_status,
)
from behave_modern_json_report.validator import ValidationResult, _structural_validate


def _step(status=STATUS_PASSED, **kwargs):
    base = {
        "id": "step-1",
        "keyword": "Given",
        "text": "a step",
        "status": status,
        "duration": 0.1,
        "location": Location(filename="f.feature", line=5),
    }
    base.update(kwargs)
    return Step(**base)


def _report(steps, **scn_kwargs):
    scenario = Scenario(id="sc-1", name="S", feature_id="f-1", steps=steps, **scn_kwargs)
    feature = Feature(id="f-1", name="F", scenarios=[scenario])
    return ExecutionReport(
        schema_version=SCHEMA_VERSION,
        execution=Execution(execution_id="e-1"),
        statistics=Statistics(),
        environment=Environment(),
        features=[feature],
        metadata=Metadata(),
    )


# ---------------------------------------------------------------------------
# Bug 1: formatters must expose embedding() for context.attach()
# ---------------------------------------------------------------------------


class TestEmbeddingMethod:
    @pytest.mark.parametrize("cls", [ModernJSONFormatter, CucumberJSONFormatter])
    def test_formatter_has_embedding(self, cls):
        fmt = cls(stream=io.StringIO())
        assert hasattr(fmt, "embedding")

    @pytest.mark.parametrize("cls", [ModernJSONFormatter, CucumberJSONFormatter])
    def test_embedding_buffers_attachment(self, cls):
        fmt = cls(stream=io.StringIO())
        fmt._collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line=1))
        fmt._collector.start_scenario(
            SimpleNamespace(name="S", tags=[], filename="f", line=2, examples=None)
        )
        fmt.embedding("text/plain", b"payload")
        fmt._collector.start_step(
            SimpleNamespace(keyword="Given", name="s", status="passed", filename="f", line=3)
        )
        fmt._collector.end_step(
            SimpleNamespace(
                keyword="Given", name="s", status="passed", filename="f", line=3, duration=0.1
            )
        )
        report = fmt._collector.finalize()
        atts = report.features[0].scenarios[0].steps[0].attachments
        assert len(atts) == 1
        assert atts[0].mime_type == "text/plain"
        assert base64.b64decode(atts[0].content) == b"payload"

    def test_embedding_handles_non_bytes(self):
        fmt = ModernJSONFormatter(stream=io.StringIO())
        fmt._collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line=1))
        fmt._collector.start_scenario(
            SimpleNamespace(name="S", tags=[], filename="f", line=2, examples=None)
        )
        fmt.embedding("text/plain", "a string")
        fmt.embedding(None, None)  # must not raise
        report = fmt._collector.finalize()
        assert len(report.features[0].scenarios[0].steps) == 0  # buffered until a step resolves


# ---------------------------------------------------------------------------
# Bug 2: attachments/logs must reach every compatible formatter
# ---------------------------------------------------------------------------


class TestBroadcastToAllFormatters:
    def test_two_formatters_both_receive_attachment(self):
        fmt1, fmt2 = (
            ModernJSONFormatter(stream=io.StringIO()),
            ModernJSONFormatter(stream=io.StringIO()),
        )
        ctx = SimpleNamespace(_runner=SimpleNamespace(formatters=[fmt1, fmt2]))
        attach.attach_text(ctx, "hello")
        assert len(fmt1._collector._pending) == 1
        assert len(fmt2._collector._pending) == 1

    def test_two_formatters_both_receive_log(self):
        fmt1, fmt2 = (
            ModernJSONFormatter(stream=io.StringIO()),
            CucumberJSONFormatter(stream=io.StringIO()),
        )
        ctx = SimpleNamespace(_runner=SimpleNamespace(formatters=[fmt1, fmt2]))
        attach.log(ctx, "msg")
        assert len(fmt1._collector._pending) == 1
        assert len(fmt2._collector._pending) == 1

    def test_incompatible_formatters_are_skipped(self):
        good = ModernJSONFormatter(stream=io.StringIO())
        bad = object()  # no add_attachment
        ctx = SimpleNamespace(_runner=SimpleNamespace(formatters=[bad, good]))
        attach.attach_text(ctx, "x")
        assert len(good._collector._pending) == 1


# ---------------------------------------------------------------------------
# Bug 3: scenario.background must include inherited background steps
# ---------------------------------------------------------------------------


def _behave_bg_step(name, status="passed"):
    return SimpleNamespace(
        keyword="Given",
        name=name,
        status=status,
        duration=0.01,
        filename="f.feature",
        line=4,
        error_message=None,
        doc_string=None,
        table=None,
    )


class TestInheritedBackground:
    def test_rule_scenario_gets_feature_and_rule_bg_steps(self):
        """Behave merges feature bg into rule bg via inherited_steps; the
        per-scenario background must contain both."""
        collector = Collector()
        feature_bg = SimpleNamespace(
            name="feat bg",
            keyword="Background",
            filename="f.feature",
            line=2,
            steps=[_behave_bg_step("feature bg step")],
        )
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="f.feature",
            line=1,
            description=None,
            background=feature_bg,
        )
        rule_bg = SimpleNamespace(
            name="rule bg",
            keyword="Background",
            filename="f.feature",
            line=10,
            steps=[_behave_bg_step("rule bg step")],
            # Behave exposes inherited_steps + all_steps on Background
            inherited_background=feature_bg,
            all_steps=feature_bg.steps + [_behave_bg_step("rule bg step")],
        )
        rule = SimpleNamespace(
            name="R",
            tags=[],
            filename="f.feature",
            line=9,
            description=None,
            background=rule_bg,
        )
        scenario = SimpleNamespace(
            name="S",
            tags=[],
            filename="f.feature",
            line=12,
            description=None,
            examples=None,
            background=rule_bg,
        )
        collector.start_feature(feature)
        collector.start_rule(rule)
        sc = collector.start_scenario(scenario)
        assert sc.background is not None
        names = [s.text for s in sc.background.steps]
        assert "feature bg step" in names
        assert "rule bg step" in names

    def test_rule_without_declared_bg_gets_inherited_feature_bg(self):
        """A rule's default (empty) background still inherits the feature bg."""
        collector = Collector()
        feature_bg = SimpleNamespace(
            name="feat bg",
            keyword="Background",
            filename="f.feature",
            line=2,
            steps=[_behave_bg_step("feature bg step")],
        )
        feature = SimpleNamespace(
            name="F",
            tags=[],
            filename="f.feature",
            line=1,
            description=None,
            background=feature_bg,
        )
        default_rule_bg = SimpleNamespace(
            name="",
            keyword="Background",
            filename="f.feature",
            line=8,
            steps=[],
            inherited_background=feature_bg,
            all_steps=list(feature_bg.steps),
        )
        rule = SimpleNamespace(
            name="R",
            tags=[],
            filename="f.feature",
            line=8,
            description=None,
            background=default_rule_bg,
        )
        scenario = SimpleNamespace(
            name="S",
            tags=[],
            filename="f.feature",
            line=11,
            description=None,
            examples=None,
            background=default_rule_bg,
        )
        collector.start_feature(feature)
        rule_obj = collector.start_rule(rule)
        # No declared steps → no rule background definition in the report.
        assert rule_obj.background is None
        sc = collector.start_scenario(scenario)
        assert sc.background is not None
        assert [s.text for s in sc.background.steps] == ["feature bg step"]


# ---------------------------------------------------------------------------
# Bug 4: cucumber elements must follow document order
# ---------------------------------------------------------------------------


class TestCucumberElementOrder:
    def test_mixed_scenarios_keep_file_order(self):
        top1 = Scenario(id="sc-1", name="Top1", feature_id="f", steps=[_step()])
        rule_sc = Scenario(
            id="sc-2",
            name="RuleScn",
            feature_id="f",
            rule="R",
            rule_id="r-1",
            steps=[_step()],
        )
        top2 = Scenario(id="sc-3", name="Top2", feature_id="f", steps=[_step()])
        rule = Rule(id="r-1", name="R", feature_id="f", scenarios=[rule_sc])
        feature = Feature(id="f", name="F", scenarios=[top1, rule_sc, top2], rules=[rule])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        elements = json.loads(serialize_cucumber(report))[0]["elements"]
        names = [e["name"] for e in elements if e["type"] == "scenario"]
        assert names == ["Top1", "RuleScn", "Top2"]

    def test_rule_scenarios_only_in_rule_list_are_still_emitted(self):
        """Hand-built models that skip feature.scenarios must not lose data."""
        rule_sc = Scenario(
            id="sc-r",
            name="RuleOnly",
            feature_id="f",
            rule="R",
            rule_id="r-1",
            steps=[_step()],
        )
        top = Scenario(id="sc-t", name="Top", feature_id="f", steps=[_step()])
        rule = Rule(id="r-1", name="R", feature_id="f", scenarios=[rule_sc])
        feature = Feature(id="f", name="F", scenarios=[top], rules=[rule])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        elements = json.loads(serialize_cucumber(report))[0]["elements"]
        names = [e["name"] for e in elements if e["type"] == "scenario"]
        assert names == ["Top", "RuleOnly"]


# ---------------------------------------------------------------------------
# Bug 5: normalize_status must map Behave 1.3.x runtime statuses
# ---------------------------------------------------------------------------


class TestNormalizeStatus:
    def test_pending_warn_maps_to_pending(self):
        assert normalize_status("pending_warn") == STATUS_PENDING

    def test_untested_variants_map_to_untested(self):
        assert normalize_status("untested_pending") == "untested"
        assert normalize_status("untested_undefined") == "untested"
        assert normalize_status("executing") == "untested"
        assert normalize_status("unknown") == "untested"

    def test_enum_like_object(self):
        status = SimpleNamespace(name="PASSED")
        assert normalize_status(status) == STATUS_PASSED

    def test_object_with_non_str_name(self):
        status = SimpleNamespace(name=5)
        assert normalize_status(status) == "untested"  # must not raise


# ---------------------------------------------------------------------------
# Bug 6: a real 0.0 duration must not be replaced by a monotonic fallback
# ---------------------------------------------------------------------------


class TestZeroDuration:
    def test_step_zero_duration_preserved(self):
        collector = Collector()
        collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line=1))
        collector.start_scenario(
            SimpleNamespace(name="S", tags=[], filename="f", line=2, examples=None)
        )
        behave_step = SimpleNamespace(
            keyword="Given", name="s", status="passed", filename="f", line=3, duration=0.0
        )
        import time

        collector.start_step(behave_step)
        time.sleep(0.01)  # make the monotonic fallback measurably non-zero
        step = collector.end_step(behave_step)
        assert step.duration == 0.0

    def test_scenario_zero_duration_preserved(self):
        collector = Collector()
        collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line=1))
        behave_scn = SimpleNamespace(
            name="S",
            tags=[],
            filename="f",
            line=2,
            examples=None,
            duration=0.0,
            status="passed",
        )
        collector.start_scenario(behave_scn)
        sc = collector.end_scenario(behave_scn)
        assert sc.duration == 0.0


# ---------------------------------------------------------------------------
# Bug 7: os.getcwd() failure must not break collection / environment
# ---------------------------------------------------------------------------


class TestGetcwdFailure:
    def test_collector_survives_deleted_cwd(self, monkeypatch):
        monkeypatch.setattr(
            "behave_modern_json_report.collector.os.getcwd",
            lambda: (_ for _ in ()).throw(FileNotFoundError("cwd deleted")),
        )
        collector = Collector()
        assert collector._working_directory is None

    def test_detect_environment_survives_deleted_cwd(self, monkeypatch):
        monkeypatch.setattr(
            "behave_modern_json_report.environment.os.getcwd",
            lambda: (_ for _ in ()).throw(FileNotFoundError("cwd deleted")),
        )
        from behave_modern_json_report.environment import detect_environment

        env = detect_environment()
        assert env.cwd is None


# ---------------------------------------------------------------------------
# Bug 8: non-finite floats must not produce invalid JSON
# ---------------------------------------------------------------------------


class TestNonFiniteFloats:
    def test_nan_duration_serializes_as_valid_json(self):
        report = _report([_step(duration=float("nan"))])
        payload = Serializer().to_json(report)
        assert "NaN" not in payload
        data = json.loads(payload)
        assert data["features"][0]["scenarios"][0]["steps"][0]["duration"] == 0.0

    def test_inf_duration_serializes_as_valid_json(self):
        report = _report([_step(duration=float("inf"))])
        payload = Serializer().to_json(report)
        assert "Infinity" not in payload
        data = json.loads(payload)
        assert data["features"][0]["scenarios"][0]["steps"][0]["duration"] == 0.0

    def test_non_serializable_metadata_does_not_crash(self):
        report = _report([_step()])
        report.metadata = Metadata(data={"blob": b"\x00\x01"})
        payload = Serializer().to_json(report)
        assert json.loads(payload)["metadata"]["blob"] == "b'\\x00\\x01'"

    def test_cucumber_nan_duration_is_safe(self):
        report = _report([_step(duration=float("nan"))])
        data = json.loads(serialize_cucumber(report))
        assert data[0]["elements"][0]["steps"][0]["result"]["duration"] == 0


# ---------------------------------------------------------------------------
# Bug 9: structural validator — bool is not a number; status enum enforced
# ---------------------------------------------------------------------------


class TestStructuralValidator:
    def _validate(self, data):
        result = ValidationResult(valid=True)
        _structural_validate(data, result)
        return result

    def test_bool_duration_rejected(self):
        data = Serializer().to_dict(_report([_step()]))
        data["features"][0]["scenarios"][0]["steps"][0]["duration"] = True
        assert not self._validate(data).valid

    def test_invalid_status_rejected(self):
        data = Serializer().to_dict(_report([_step()]))
        data["features"][0]["scenarios"][0]["steps"][0]["status"] = "bogus"
        result = self._validate(data)
        assert not result.valid
        assert any("status" in e.path for e in result.errors)

    def test_invalid_execution_status_rejected(self):
        data = Serializer().to_dict(_report([_step()]))
        data["execution"]["status"] = "exploded"
        assert not self._validate(data).valid

    def test_negative_duration_rejected(self):
        data = Serializer().to_dict(_report([_step()]))
        data["features"][0]["scenarios"][0]["steps"][0]["duration"] = -1.5
        assert not self._validate(data).valid

    def test_pass_rate_above_one_rejected(self):
        data = Serializer().to_dict(_report([_step()]))
        data["statistics"]["passRate"] = 1.5
        assert not self._validate(data).valid

    def test_valid_report_still_passes(self):
        data = Serializer().to_dict(_report([_step()]))
        assert self._validate(data).valid


# ---------------------------------------------------------------------------
# Bug 10: _pending items must survive to the last step at finalize
# ---------------------------------------------------------------------------


class TestPendingFlushAtFinalize:
    def test_after_all_attachment_lands_on_last_step(self):
        collector = Collector()
        collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line=1))
        collector.start_scenario(
            SimpleNamespace(name="S", tags=[], filename="f", line=2, examples=None)
        )
        behave_step = SimpleNamespace(
            keyword="Given", name="s", status="passed", filename="f", line=3, duration=0.1
        )
        collector.start_step(behave_step)
        collector.end_step(behave_step)
        collector.end_scenario(None)
        collector.end_feature(None)
        # Simulates an after_all hook adding data after everything ended.
        collector.add_attachment(name="late.txt", mime_type="text/plain", content="late")
        collector.add_log("INFO", "late log")
        report = collector.finalize()
        last_step = report.features[0].scenarios[0].steps[-1]
        assert [a.name for a in last_step.attachments] == ["late.txt"]
        assert [lg.message for lg in last_step.logs] == ["late log"]

    def test_finalize_with_no_steps_does_not_crash(self):
        collector = Collector()
        collector.add_log("INFO", "orphan")
        report = collector.finalize()  # no crash; item is dropped
        assert report.features == []


# ---------------------------------------------------------------------------
# Bug 11: external attachments must not stuff path into embedding data
# ---------------------------------------------------------------------------


class TestExternalAttachmentEmbeddings:
    def test_path_only_attachment_skipped_in_embeddings(self):
        step = _step(
            attachments=[
                Attachment(
                    id="a1",
                    name="f.png",
                    mime_type="image/png",
                    encoding="external",
                    path="C:/shots/f.png",
                    content=None,
                )
            ]
        )
        data = json.loads(serialize_cucumber(_report([step])))
        assert "embeddings" not in data[0]["elements"][0]["steps"][0]

    def test_raw_attachment_embedded_as_base64(self):
        step = _step(
            attachments=[
                Attachment(
                    id="a1",
                    name="n.txt",
                    mime_type="text/plain",
                    encoding="raw",
                    content="hello",
                )
            ]
        )
        data = json.loads(serialize_cucumber(_report([step])))
        emb = data[0]["elements"][0]["steps"][0]["embeddings"][0]
        assert base64.b64decode(emb["data"]) == b"hello"


# ---------------------------------------------------------------------------
# Bug 12: _location must tolerate a non-numeric line
# ---------------------------------------------------------------------------


class TestLocationRobustness:
    def test_non_numeric_line_becomes_zero(self):
        collector = Collector()
        step = collector.start_feature(SimpleNamespace(name="F", tags=[], filename="f", line="abc"))
        assert step.line is None  # schema requires integer|null — "abc" dropped
        collector.start_scenario(
            SimpleNamespace(name="S", tags=[], filename="f", line=2, examples=None)
        )
        model_step = collector.start_step(
            SimpleNamespace(keyword="Given", name="s", filename="f", line="xyz")
        )
        assert model_step.location.line == 0


# ---------------------------------------------------------------------------
# Bug 13: dead runner proxy / non-bytes screenshot data
# ---------------------------------------------------------------------------


class TestAttachRobustness:
    def test_dead_weakref_context_does_not_raise(self):
        """Behave's ``context._runner`` is a weak proxy; once the runner is
        gone attribute access raises ReferenceError instead of returning None."""

        class Ctx:
            @property
            def _runner(self):
                raise ReferenceError("dead proxy")

        attach.attach_text(Ctx(), "x")  # must not raise
        attach.log(Ctx(), "x")
        attach.attach_screenshot(Ctx(), b"data")

    def test_screenshot_non_bytes_data_coerced(self):
        class WeirdDriver:
            def get_screenshot_as_png(self):
                return {"unexpected": "dict"}

        fmt = ModernJSONFormatter(stream=io.StringIO())
        ctx = SimpleNamespace(_runner=SimpleNamespace(formatters=[fmt]))
        attach.attach_screenshot(ctx, WeirdDriver())
        assert len(fmt._collector._pending) == 1

    def test_screenshot_sniffs_jpeg_bytes(self):
        fmt = ModernJSONFormatter(stream=io.StringIO())
        ctx = SimpleNamespace(_runner=SimpleNamespace(formatters=[fmt]))
        attach.attach_screenshot(ctx, b"\xff\xd8\xff\xe0jpegdata", name="shot.png")
        att = fmt._collector._pending[0][1]
        assert att.mime_type == "image/jpeg"


# ---------------------------------------------------------------------------
# Bug 14: rules emptied by exclude_passed_scenarios must be dropped
# ---------------------------------------------------------------------------


class TestExcludePassedDropsEmptyRules:
    def test_rule_with_only_passed_scenarios_dropped(self):
        passed = Scenario(
            id="sc-p", name="P", feature_id="f", status=STATUS_PASSED, steps=[_step()]
        )
        failed = Scenario(
            id="sc-f", name="F", feature_id="f", status=STATUS_FAILED, steps=[_step()]
        )
        rule = Rule(id="r-1", name="R", feature_id="f", scenarios=[passed])
        feature = Feature(id="f", name="F", scenarios=[passed, failed], rules=[rule])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        data = Serializer(SerializerOptions(exclude_passed_scenarios=True)).to_dict(report)
        assert "rules" not in data["features"][0]
        assert [s["id"] for s in data["features"][0]["scenarios"]] == ["sc-f"]


# ---------------------------------------------------------------------------
# Bug 15: passRate must count error/undefined/pending steps as non-passing
# ---------------------------------------------------------------------------


class TestPassRate:
    def test_error_step_lowers_pass_rate(self):
        report = _report(
            [_step(), _step(status="error")],
        )
        report.statistics = compute_statistics(report)
        assert report.statistics.pass_rate == 0.5

    def test_undefined_step_lowers_pass_rate(self):
        report = _report([_step(), _step(status="undefined")])
        report.statistics = compute_statistics(report)
        assert report.statistics.pass_rate == 0.5

    def test_skipped_step_excluded_from_rate(self):
        report = _report([_step(), _step(status="skipped")])
        report.statistics = compute_statistics(report)
        assert report.statistics.pass_rate == 1.0


# ---------------------------------------------------------------------------
# Bug 16: cucumber _duration must survive hostile inputs
# ---------------------------------------------------------------------------


class TestCucumberDuration:
    def test_negative_duration_clamped(self):
        report = _report([_step(duration=-5.0)])
        data = json.loads(serialize_cucumber(report))
        assert data[0]["elements"][0]["steps"][0]["result"]["duration"] == 0

    def test_inf_duration_does_not_raise(self):
        report = _report([_step(duration=float("inf"))])
        data = json.loads(serialize_cucumber(report))
        assert data[0]["elements"][0]["steps"][0]["result"]["duration"] == 0


# ---------------------------------------------------------------------------
# Bug 17: statistics must count scenarios that only live in rule.scenarios
# ---------------------------------------------------------------------------


class TestStatisticsRuleOnlyScenarios:
    def test_rule_only_scenario_counted(self):
        sc = Scenario(
            id="sc-r",
            name="R",
            feature_id="f",
            status=STATUS_FAILED,
            steps=[_step(status=STATUS_FAILED)],
        )
        top = Scenario(id="sc-t", name="T", feature_id="f", steps=[_step()])
        rule = Rule(id="r-1", name="Rule", feature_id="f", scenarios=[sc])
        feature = Feature(id="f", name="F", scenarios=[top], rules=[rule])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        stats = compute_statistics(report)
        assert stats.scenarios == 2
        assert stats.failed == 1

    def test_shared_objects_not_double_counted(self):
        sc = Scenario(id="sc-1", name="S", feature_id="f", steps=[_step()])
        rule = Rule(id="r-1", name="Rule", feature_id="f", scenarios=[sc])
        feature = Feature(id="f", name="F", scenarios=[sc], rules=[rule])
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[feature],
            metadata=Metadata(),
        )
        stats = compute_statistics(report)
        assert stats.scenarios == 1
        assert stats.steps == 1

    def test_feature_status_covers_rule_only_scenarios(self):
        sc = Scenario(id="sc-r", name="R", feature_id="f", status=STATUS_FAILED, steps=[_step()])
        top = Scenario(id="sc-t", name="T", feature_id="f", steps=[_step()])
        rule = Rule(id="r-1", name="Rule", feature_id="f", scenarios=[sc])
        feature = Feature(id="f", name="F", scenarios=[top], rules=[rule])
        assert feature_status(feature) == STATUS_FAILED


# ---------------------------------------------------------------------------
# Bug 18: config.get() never exists on behave's Configuration — formatter
# options must be read from mjr.* userdata keys
# ---------------------------------------------------------------------------


class TestUserdataOptions:
    def test_mjr_options_read_from_userdata(self):
        from behave_modern_json_report.formatter import _options_from_config

        config = SimpleNamespace(
            userdata={
                "mjr.pretty": "false",
                "mjr.exclude_passed_scenarios": "true",
                "mjr.indent": "4",
            }
        )
        opts = _options_from_config(config)
        assert opts.pretty is False
        assert opts.exclude_passed_scenarios is True
        assert opts.indent == 4

    def test_cucumber_mjr_options_read_from_userdata(self):
        from behave_modern_json_report.cucumber_formatter import (
            _cucumber_options_from_config,
        )

        config = SimpleNamespace(userdata={"mjr.duration_in_nanos": "false"})
        opts = _cucumber_options_from_config(config)
        assert opts.duration_in_nanos is False

    def test_real_behave_configuration(self):
        """behave's Configuration has no .get — options come from userdata."""
        pytest.importorskip("behave")
        from behave.configuration import Configuration

        from behave_modern_json_report.formatter import _options_from_config

        config = Configuration()
        config.userdata = {"mjr.pretty": "false"}
        opts = _options_from_config(config)
        assert opts.pretty is False

    def test_option_keys_excluded_from_metadata(self):
        config = SimpleNamespace(userdata={"mjr.pretty": "false", "mjr.branch": "dev"})
        fmt = ModernJSONFormatter(config=config, stream=io.StringIO())
        assert fmt._collector._metadata == {"branch": "dev"}

    def test_config_get_callable_still_works(self):
        """Non-Behave producers exposing config.get(key) keep working."""
        config = SimpleNamespace(get=lambda key: {"pretty": "false"}.get(key))
        from behave_modern_json_report.formatter import _options_from_config

        assert _options_from_config(config).pretty is False


# ---------------------------------------------------------------------------
# Bug 19: environment_extra must survive string/non-dict userdata values
# ---------------------------------------------------------------------------


class TestEnvironmentExtra:
    def test_json_string_parsed(self):
        collector = Collector(metadata={"environment_extra": '{"region": "eu"}'})
        report = collector.finalize()
        assert report.environment.extra.get("region") == "eu"

    def test_non_dict_value_ignored(self):
        collector = Collector(metadata={"environment_extra": "not a dict"})
        report = collector.finalize()  # must not crash
        assert report.environment.extra.get("environment_extra") is None

    def test_int_value_ignored(self):
        collector = Collector(metadata={"environment_extra": 42})
        report = collector.finalize()
        assert "python_implementation" in report.environment.extra


# ---------------------------------------------------------------------------
# Bug 20: None report / None collection fields must fail cleanly
# ---------------------------------------------------------------------------


class TestNoneGuards:
    def test_serialize_none_raises_typeerror(self):
        with pytest.raises(TypeError):
            Serializer().to_dict(None)

    def test_cucumber_none_raises_typeerror(self):
        with pytest.raises(TypeError):
            serialize_cucumber(None)

    def test_none_feature_lists_serialize_empty(self):
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=[Feature(id="f", name="F", scenarios=None, rules=None, tags=None)],
            metadata=Metadata(),
        )
        data = Serializer().to_dict(report)
        assert data["features"][0]["scenarios"] == []
        assert "rules" not in data["features"][0]
        cuc = json.loads(serialize_cucumber(report))
        assert cuc[0]["elements"] == []

    @pytest.mark.parametrize("bad", ["nope", {"a": 1}, 42])
    def test_non_list_features_raises_typeerror(self, bad):
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=bad,
            metadata=Metadata(),
        )
        with pytest.raises(TypeError, match="features"):
            Serializer().to_dict(report)
        with pytest.raises(TypeError, match="features"):
            serialize_cucumber(report)

    @pytest.mark.parametrize(
        "field_name",
        ["execution", "statistics", "environment", "metadata"],
    )
    def test_wrong_type_required_field_raises_typeerror(self, field_name):
        report = _minimal_report(**{field_name: "nope"})
        with pytest.raises(TypeError, match=field_name):
            Serializer().to_dict(report)

    def test_compute_statistics_rejects_non_report(self):
        from behave_modern_json_report.statistics import compute_statistics

        with pytest.raises(TypeError):
            compute_statistics(None)
        with pytest.raises(TypeError):
            compute_statistics("nope")

    def test_none_report_features_serializes_empty(self):
        report = ExecutionReport(
            schema_version=SCHEMA_VERSION,
            execution=Execution(execution_id="e"),
            statistics=Statistics(),
            environment=Environment(),
            features=None,
            metadata=Metadata(),
        )
        assert Serializer().to_dict(report)["features"] == []
        assert json.loads(serialize_cucumber(report)) == []


# ---------------------------------------------------------------------------
# Bug 21: programmatic eof() flushed and closed — later features were silently
# dropped from the output
# ---------------------------------------------------------------------------


def _drive(formatter, feature_name: str, scenario_name: str) -> None:
    feature = SimpleNamespace(
        name=feature_name,
        filename=f"{feature_name}.feature",
        keyword="Feature",
        description=[],
        tags=[],
        status="passed",
        duration=0.0,
        scenarios=[],
        rules=[],
        background=None,
        location=None,
    )
    scenario = SimpleNamespace(
        name=scenario_name,
        filename=feature.filename,
        keyword="Scenario",
        tags=[],
        status="passed",
        duration=0.0,
        steps=[],
        all_steps=[],
        background=None,
        feature=feature,
        rule=None,
        location=None,
    )
    formatter.feature(feature)
    formatter.scenario(scenario)
    formatter.eof()


class TestEofReopen:
    def test_features_after_eof_not_lost(self):
        stream = io.StringIO()
        fmt = ModernJSONFormatter(stream=stream, options=SerializerOptions(pretty=False))
        _drive(fmt, "one", "s1")
        _drive(fmt, "two", "s2")
        fmt.close()
        data = json.loads(stream.getvalue())
        assert [f["name"] for f in data["features"]] == ["one", "two"]

    def test_output_remains_single_document(self):
        stream = io.StringIO()
        fmt = ModernJSONFormatter(stream=stream, options=SerializerOptions(pretty=False))
        _drive(fmt, "one", "s1")
        _drive(fmt, "two", "s2")
        fmt.close()
        # seekable streams are rewritten in place: exactly one JSON doc
        assert stream.getvalue().count('"schemaVersion"') == 1

    def test_cucumber_features_after_eof_not_lost(self):
        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream, options=None)
        _drive(fmt, "one", "s1")
        _drive(fmt, "two", "s2")
        fmt.close()
        data = json.loads(stream.getvalue())
        assert [f["name"] for f in data] == ["one", "two"]

    def test_non_seekable_stream_still_writes_all_data(self):
        class _NoSeek(io.StringIO):
            def seekable(self):
                return False

            def seek(self, *a, **k):
                raise OSError("not seekable")

        stream = _NoSeek()
        fmt = ModernJSONFormatter(stream=stream, options=SerializerOptions(pretty=False))
        _drive(fmt, "one", "s1")
        _drive(fmt, "two", "s2")
        fmt.close()
        # appended documents: second doc must still contain feature "two"
        assert '"two"' in stream.getvalue()


# ---------------------------------------------------------------------------
# Bug 22: one hostile formatter broke attachment broadcast for all the others;
# the same instance listed twice received duplicates
# ---------------------------------------------------------------------------


class _RecordingFormatter:
    def __init__(self) -> None:
        self.attachments: list[dict] = []
        self.logs: list[dict] = []

    def add_attachment(self, **kwargs) -> None:
        self.attachments.append(kwargs)

    def add_log(self, **kwargs) -> None:
        self.logs.append(kwargs)


def _ctx(*formatters):
    return SimpleNamespace(_runner=SimpleNamespace(formatters=list(formatters)))


class TestBroadcastResilience:
    def test_hostile_formatter_does_not_starve_others(self):
        class Evil:
            def __getattr__(self, name):
                raise RuntimeError("boom")

        good = _RecordingFormatter()
        attach.attach_text(_ctx(Evil(), good), "hi")
        assert len(good.attachments) == 1

    def test_same_instance_not_called_twice(self):
        fmt = _RecordingFormatter()
        attach.attach_text(_ctx(fmt, fmt), "hi")
        assert len(fmt.attachments) == 1

    def test_raising_add_attachment_does_not_starve_others(self):
        class Broken(_RecordingFormatter):
            def add_attachment(self, **kwargs):
                raise RuntimeError("nope")

        good = _RecordingFormatter()
        attach.attach_text(_ctx(Broken(), good), "hi")
        assert len(good.attachments) == 1

    def test_raising_add_log_does_not_starve_others(self):
        class Broken(_RecordingFormatter):
            def add_log(self, **kwargs):
                raise RuntimeError("nope")

        good = _RecordingFormatter()
        attach.log(_ctx(Broken(), good), "msg")
        assert len(good.logs) == 1


# ---------------------------------------------------------------------------
# Bug 23: git remote URLs with embedded credentials leaked into reports
# ---------------------------------------------------------------------------


class TestRemoteSanitization:
    def test_token_in_url_stripped(self):
        from behave_modern_json_report.environment import _sanitize_remote

        url = "https://oauth2:SECRET_TOKEN@gitlab.com/org/repo.git"
        assert _sanitize_remote(url) == "https://gitlab.com/org/repo.git"

    def test_user_in_url_stripped(self):
        from behave_modern_json_report.environment import _sanitize_remote

        assert (
            _sanitize_remote("https://user@github.com/org/repo.git")
            == "https://github.com/org/repo.git"
        )

    def test_scp_style_preserved(self):
        from behave_modern_json_report.environment import _sanitize_remote

        url = "git@github.com:org/repo.git"
        assert _sanitize_remote(url) == url

    def test_capture_git_info_sanitizes(self, monkeypatch):
        import subprocess

        import behave_modern_json_report.environment as env_mod

        def fake_run(cmd, **kwargs):
            if "remote" in cmd:
                return SimpleNamespace(returncode=0, stdout="https://u:t@h/r\n", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        info = env_mod._capture_git_info()
        assert info["remote"] == "https://h/r"


# ---------------------------------------------------------------------------
# Bug 24: normalize_status crashed on objects with a hostile ``name``
# ---------------------------------------------------------------------------


class TestNormalizeStatusHostile:
    def test_name_descriptor_raising(self):
        class Hostile:
            @property
            def name(self):
                raise RuntimeError("boom")

        assert normalize_status(Hostile()) == "untested"


# ---------------------------------------------------------------------------
# Bug 25: after_step attachments bound to the NEXT step instead of the one
# that just finished (behave runs after_step after the result() event)
# ---------------------------------------------------------------------------


def _behave_step(name="step"):
    return SimpleNamespace(
        keyword="Then",
        name=name,
        status="passed",
        duration=0.01,
        error=None,
        exception=None,
        filename="f.feature",
        line=1,
        doc_string=None,
        table=None,
    )


class TestAfterStepAttribution:
    def _scenario(self):
        return SimpleNamespace(
            name="sc",
            filename="f.feature",
            keyword="Scenario",
            tags=[],
            status="passed",
            duration=0.0,
            steps=[],
            all_steps=[],
            background=None,
            feature=SimpleNamespace(name="F"),
            rule=None,
            location=None,
        )

    def _collector(self):
        c = Collector()
        c.start_feature(
            SimpleNamespace(
                name="F", filename="f.feature", keyword="Feature", tags=[], background=None
            )
        )
        c.start_scenario(self._scenario())
        return c

    def test_after_step_attachment_lands_on_finished_step(self):
        c = self._collector()
        s1, s2 = _behave_step("s1"), _behave_step("s2")
        c.start_step(s1)
        c.end_step(s1)
        # behave's after_step hook for s1 runs here, before step(s2) event
        c.add_attachment(name="shot.png", mime_type="image/png", content="x", encoding="base64")
        c.start_step(s2)
        c.end_step(s2)
        sc = c._features[0].scenarios[0]
        assert len(sc.steps[0].attachments) == 1
        assert len(sc.steps[1].attachments) == 0

    def test_before_step_log_lands_on_coming_step(self):
        c = self._collector()
        s1, s2 = _behave_step("s1"), _behave_step("s2")
        c.start_step(s1)
        c.end_step(s1)
        c.start_step(s2)
        # behave's before_step hook for s2 runs after the step(s2) event
        c.add_log(level="INFO", message="about to run s2")
        c.end_step(s2)
        sc = c._features[0].scenarios[0]
        assert len(sc.steps[0].logs) == 0
        assert len(sc.steps[1].logs) == 1

    def test_before_scenario_log_lands_on_first_step(self):
        c = self._collector()
        s1 = _behave_step("s1")
        # before_scenario hook (runs after the scenario() event)
        c.add_log(level="INFO", message="scenario starting")
        c.start_step(s1)
        c.end_step(s1)
        sc = c._features[0].scenarios[0]
        assert len(sc.steps[0].logs) == 1

    def test_pending_does_not_leak_across_scenarios(self):
        c = self._collector()
        s1 = _behave_step("s1")
        c.start_step(s1)
        c.end_step(s1)
        # after_scenario-style item: flushed at scenario end, not to the next one
        c.add_log(level="INFO", message="scenario done")
        c.end_scenario(None)
        c.start_scenario(self._scenario())
        s2 = _behave_step("s2")
        c.start_step(s2)
        c.end_step(s2)
        sc1, sc2 = c._features[0].scenarios
        assert len(sc1.steps[0].logs) == 1
        assert len(sc2.steps[0].logs) == 0


# ---------------------------------------------------------------------------
# Bug 26: cyclic metadata caused RecursionError; required fields raised
# AttributeError; negative indent reached json.dumps
# ---------------------------------------------------------------------------


def _minimal_report(**overrides):
    kwargs = {
        "schema_version": SCHEMA_VERSION,
        "execution": Execution(execution_id="e"),
        "statistics": Statistics(),
        "environment": Environment(),
        "features": [],
        "metadata": Metadata(),
    }
    kwargs.update(overrides)
    return ExecutionReport(**kwargs)


class TestSerializerHardening:
    def test_cyclic_metadata_no_recursion_error(self):
        data: dict = {}
        data["self"] = data
        report = _minimal_report(metadata=Metadata(data=data))
        out = Serializer(SerializerOptions(pretty=False)).to_json(report)
        json.loads(out)  # valid JSON, cycle became a repr string

    def test_cyclic_list_no_recursion_error(self):
        lst: list = []
        lst.append(lst)
        report = _minimal_report(metadata=Metadata(data={"cycle": lst}))
        out = Serializer(SerializerOptions(pretty=False)).to_json(report)
        json.loads(out)

    @pytest.mark.parametrize(
        "field_name",
        ["execution", "statistics", "environment", "metadata"],
    )
    def test_none_required_field_raises_typeerror(self, field_name):
        report = _minimal_report(**{field_name: None})
        with pytest.raises(TypeError, match=field_name):
            Serializer().to_dict(report)

    def test_negative_indent_clamped(self):
        from behave_modern_json_report.formatter import _options_from_config

        config = SimpleNamespace(userdata={"mjr.indent": "-5"})
        assert _options_from_config(config).indent == 0

    def test_scenario_steps_none_serializes(self):
        report = _minimal_report(
            features=[
                Feature(
                    id="f",
                    name="F",
                    scenarios=[Scenario(id="s", name="S", feature_id="f", steps=None)],
                )
            ]
        )
        data = json.loads(serialize_cucumber(report))
        assert data[0]["elements"][0]["steps"] == []

    def test_negative_durations_clamped_to_schema_minimum(self):
        # Schema requires duration >= 0 everywhere; a hand-built model with
        # negative durations must not produce an invalid report.
        step = _step()
        step.duration = -5.0
        scenario = Scenario(id="s", name="S", feature_id="f", duration=-2.0, steps=[step])
        feature = Feature(id="f", name="F", duration=-1.0, scenarios=[scenario])
        report = _minimal_report(features=[feature])
        report.execution.duration = -3.0
        report.statistics.duration = -4.0
        report.statistics.pass_rate = 7.0
        data = Serializer().to_dict(report)
        assert data["execution"]["duration"] == 0.0
        assert data["statistics"]["duration"] == 0.0
        assert data["statistics"]["passRate"] == 1.0
        f = data["features"][0]
        assert f["duration"] == 0.0
        assert f["scenarios"][0]["duration"] == 0.0
        assert f["scenarios"][0]["steps"][0]["duration"] == 0.0

    def test_statistics_ignores_negative_and_nan_model_durations(self):
        from behave_modern_json_report.statistics import compute_statistics

        step = _step()
        step.duration = float("nan")
        scenario = Scenario(id="s", name="S", feature_id="f", duration=-2.0, steps=[step])
        feature = Feature(id="f", name="F", duration=float("nan"), scenarios=[scenario])
        report = _minimal_report(features=[feature])
        stats = compute_statistics(report)
        assert math.isfinite(stats.duration)
        assert math.isfinite(stats.avg_scenario_duration)
        assert stats.avg_scenario_duration >= 0


# ---------------------------------------------------------------------------
# Bug 27: statistics crashed on None attachments/logs and let NaN durations
# poison aggregates; validator accepted NaN and a non-array "rules" key;
# validate_json raised TypeError on non-text input
# ---------------------------------------------------------------------------


def _structural_result(data):
    result = ValidationResult(valid=True)
    _structural_validate(data, result)
    return result


class TestStatisticsHardening:
    def test_none_attachments_and_logs(self):
        st = _step()
        st.attachments = None
        st.logs = None
        stats = compute_statistics(_report([st]))
        assert stats.total_attachments == 0
        assert stats.total_logs == 0

    def test_nan_duration_ignored_in_stats(self):
        st = _step(duration=float("nan"))
        stats = compute_statistics(_report([st]))
        assert stats.slowest_step_duration == 0.0
        assert stats.duration >= 0.0

    def test_none_duration_treated_as_zero(self):
        st = _step()
        st.duration = None
        stats = compute_statistics(_report([st]))
        assert stats.slowest_step_duration == 0.0


class TestValidatorHardening:
    def _valid_dict(self):
        return Serializer().to_dict(_minimal_report())

    def test_nan_rejected(self):
        data = self._valid_dict()
        data["statistics"]["duration"] = float("nan")
        result = _structural_result(data)
        assert not result.valid
        assert any("finite" in e.message for e in result.errors)

    def test_rules_must_be_array(self):
        data = self._valid_dict()
        data["features"] = [
            {
                "id": "f",
                "name": "F",
                "status": "passed",
                "duration": 0,
                "scenarios": [],
                "rules": "not-a-list",
            }
        ]
        assert not _structural_result(data).valid

    def test_validate_json_non_text_input(self):
        from behave_modern_json_report.validator import validate_json

        result = validate_json(123)  # type: ignore[arg-type]
        assert not result.valid

    def test_valid_dict_still_passes(self):
        assert _structural_result(self._valid_dict()).valid


# ---------------------------------------------------------------------------
# Coverage round — public helpers and formatter paths that had no tests
# ---------------------------------------------------------------------------


class TestAttachHelpers:
    def test_attach_file_reads_and_encodes(self, tmp_path):
        f = tmp_path / "evidence.txt"
        f.write_bytes(b"hello file")
        fmt = _RecordingFormatter()
        attach.attach_file(_ctx(fmt), f)
        assert len(fmt.attachments) == 1
        att = fmt.attachments[0]
        assert att["name"] == "evidence.txt"
        assert att["encoding"] == "base64"
        assert base64.b64decode(att["content"]) == b"hello file"
        assert att["size"] == 10

    def test_attach_file_custom_name(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"\x00")
        fmt = _RecordingFormatter()
        attach.attach_file(_ctx(fmt), f, name="custom.bin")
        assert fmt.attachments[0]["name"] == "custom.bin"

    def test_attach_file_no_formatter_no_read(self, tmp_path):
        # must not even touch the filesystem when no formatter is present
        attach.attach_file(_ctx(), tmp_path / "missing.bin")

    def test_screenshot_from_path(self, tmp_path):
        png = tmp_path / "shot.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"rest")
        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), str(png))
        assert fmt.attachments[0]["mime_type"] == "image/png"

    def test_screenshot_selenium_like(self):
        class Driver:
            def get_screenshot_as_png(self):
                return b"\x89PNG\r\n\x1a\nselenium"

        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), Driver())
        assert fmt.attachments[0]["mime_type"] == "image/png"

    def test_screenshot_playwright_like(self):
        class Page:
            def screenshot(self):
                return b"jpeg-ish"

        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), Page(), name="x.jpg")
        # not real jpg bytes -> mime falls back to name extension
        assert fmt.attachments[0]["mime_type"] == "image/jpeg"

    def test_screenshot_pil_like(self):
        class Image:
            def save(self, buf, format=None):
                buf.write(b"\x89PNG\r\n\x1a\npil")

        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), Image())
        assert fmt.attachments[0]["mime_type"] == "image/png"

    def test_screenshot_non_bytes_return_coerced(self):
        class Weird:
            def get_screenshot_as_png(self):
                return 12345

        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), Weird())
        assert len(fmt.attachments) == 1  # coerced to utf-8 "12345"

    def test_screenshot_nothing_attachable(self):
        fmt = _RecordingFormatter()
        attach.attach_screenshot(_ctx(fmt), object())
        assert fmt.attachments == []

    def test_screenshot_webp_magic(self):
        fmt = _RecordingFormatter()
        attach.attach_screenshot(
            _ctx(fmt), b"RIFF" + b"\x00" * 4 + b"WEBP" + b"rest", name="s.webp"
        )
        assert fmt.attachments[0]["mime_type"] == "image/webp"


class TestCiProvider:
    @pytest.mark.parametrize(
        ("env_var", "expected"),
        [
            ("GITHUB_ACTIONS", "github-actions"),
            ("GITLAB_CI", "gitlab-ci"),
            ("JENKINS_URL", "jenkins"),
            ("CIRCLECI", "circleci"),
            ("TRAVIS", "travis-ci"),
            ("BUILDKITE", "buildkite"),
            ("TF_BUILD", "azure-pipelines"),
            ("BITBUCKET_BUILD_NUMBER", "bitbucket-pipelines"),
            ("DRONE", "drone"),
        ],
    )
    def test_ci_detection(self, env_var, expected, monkeypatch):
        from behave_modern_json_report.utils import ci_provider

        known = {
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_URL",
            "CIRCLECI",
            "TRAVIS",
            "BUILDKITE",
            "TF_BUILD",
            "BITBUCKET_BUILD_NUMBER",
            "DRONE",
            "CI",
            "CI_NAME",
        }
        for key in known:
            monkeypatch.delenv(key, raising=False)
        value = "true" if env_var == "GITHUB_ACTIONS" else "1"
        monkeypatch.setenv(env_var, value)
        if env_var == "GITHUB_ACTIONS":
            monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert ci_provider() == expected

    def test_generic_ci(self, monkeypatch):
        from behave_modern_json_report.utils import ci_provider

        for key in (
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_URL",
            "CIRCLECI",
            "TRAVIS",
            "BUILDKITE",
            "TF_BUILD",
            "BITBUCKET_BUILD_NUMBER",
            "DRONE",
        ):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("CI", "1")
        monkeypatch.setenv("CI_NAME", "TeamCity")
        assert ci_provider() == "teamcity"


class TestFlushToPath:
    def test_stream_as_path_writes_file(self, tmp_path):
        target = tmp_path / "report.json"
        fmt = ModernJSONFormatter(stream=str(target), options=SerializerOptions(pretty=False))
        fmt.eof()
        data = json.loads(target.read_text())
        assert data["schemaVersion"] == SCHEMA_VERSION


class TestMetadataConfig:
    def test_mjr_metadata_json_from_userdata(self):
        config = SimpleNamespace(userdata={"mjr.metadata": '{"browser": "firefox", "retry": "2"}'})
        fmt = ModernJSONFormatter(config=config, stream=io.StringIO())
        assert fmt._collector._metadata["browser"] == "firefox"
        # consumed key does not leak as a literal string
        assert "metadata" not in fmt._collector._metadata

    def test_mjr_metadata_invalid_json_ignored(self):
        config = SimpleNamespace(userdata={"mjr.metadata": "not-json"})
        fmt = ModernJSONFormatter(config=config, stream=io.StringIO())
        assert fmt._collector._metadata == {}


class TestCucumberFormatterFlow:
    def _drive_step(self, fmt, name="s1"):
        s = _behave_step(name)
        fmt.step(s)
        fmt.result(s)

    def test_full_event_flow(self):
        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream)
        feature = SimpleNamespace(
            name="F",
            filename="f.feature",
            keyword="Feature",
            description=[],
            tags=[],
            status="passed",
            duration=0.0,
            scenarios=[],
            rules=[],
            background=None,
            location=None,
        )
        scenario = SimpleNamespace(
            name="sc",
            filename="f.feature",
            keyword="Scenario",
            tags=[],
            status="passed",
            duration=0.0,
            steps=[],
            all_steps=[],
            background=None,
            feature=feature,
            rule=None,
            location=None,
        )
        fmt.uri("f.feature")
        fmt.feature(feature)
        fmt.scenario(scenario)
        self._drive_step(fmt)
        fmt.scenario_result(scenario)
        fmt.feature_result(feature)
        fmt.eof()
        data = json.loads(stream.getvalue())
        assert data[0]["name"] == "F"
        assert data[0]["elements"][0]["steps"][0]["result"]["status"] == "passed"

    def test_rule_events(self):
        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream)
        feature = SimpleNamespace(
            name="F",
            filename="f.feature",
            keyword="Feature",
            description=[],
            tags=[],
            status="passed",
            duration=0.0,
            scenarios=[],
            rules=[],
            background=None,
            location=None,
        )
        rule = SimpleNamespace(
            name="R",
            keyword="Rule",
            tags=[],
            background=None,
            location=None,
            duration=0.0,
            status="passed",
        )
        scenario = SimpleNamespace(
            name="rs",
            filename="f.feature",
            keyword="Scenario",
            tags=[],
            status="passed",
            duration=0.0,
            steps=[],
            all_steps=[],
            background=None,
            feature=feature,
            rule=rule,
            location=None,
        )
        fmt.feature(feature)
        fmt.rule(rule)
        fmt.scenario(scenario)
        self._drive_step(fmt)
        fmt.rule_finished()
        fmt.eof()
        data = json.loads(stream.getvalue())
        el = data[0]["elements"][0]
        assert el.get("rule") == "R"
        assert el.get("ruleId")


class TestCollectorDocTable:
    def test_doc_string_and_table_collected(self):
        c = Collector()
        c.start_feature(
            SimpleNamespace(name="F", filename="f", keyword="Feature", tags=[], background=None)
        )
        c.start_scenario(
            SimpleNamespace(
                name="S",
                filename="f",
                keyword="Scenario",
                tags=[],
                steps=[],
                all_steps=[],
                background=None,
                feature=SimpleNamespace(name="F"),
                location=None,
            )
        )
        step = SimpleNamespace(
            keyword="Given",
            name="s",
            filename="f",
            line=1,
            doc_string=SimpleNamespace(value="doc content", content_type="text/plain", line=3),
            table=SimpleNamespace(
                headings=["a", "b"],
                rows=[
                    SimpleNamespace(cells=["1", "2"], line=4),
                    SimpleNamespace(cells=["3", "4"], line=5),
                ],
            ),
            status="passed",
            duration=0.01,
            error=None,
        )
        c.start_step(step)
        c.end_step(step)
        model_step = c._features[0].scenarios[0].steps[0]
        assert model_step.doc_string.content == "doc content"
        assert model_step.doc_string.content_type == "text/plain"
        assert model_step.data_table.headers == ["a", "b"]
        assert len(model_step.data_table.rows) == 2
        assert model_step.data_table.rows[0].cells == ["1", "2"]


class TestCollectorDeepPaths:
    def _feature(self):
        return SimpleNamespace(name="F", filename="f", keyword="Feature", tags=[], background=None)

    def _scenario(self, **kw):
        base = {
            "name": "S",
            "filename": "f",
            "keyword": "Scenario",
            "tags": [],
            "steps": [],
            "all_steps": [],
            "background": None,
            "feature": SimpleNamespace(name="F"),
            "location": None,
        }
        base.update(kw)
        return SimpleNamespace(**base)

    def test_overall_status_failed_scenario(self):
        c = Collector()
        c.start_feature(self._feature())
        c.start_scenario(self._scenario(status="failed"))
        s = _behave_step()
        s.status = "failed"
        c.start_step(s)
        c.end_step(s)
        c.end_scenario(None)
        c.end_feature(None)
        report = c.finalize()
        assert report.execution.status == "failed"

    def test_error_message_only_step(self):
        c = Collector()
        c.start_feature(self._feature())
        c.start_scenario(self._scenario())
        s = _behave_step()
        s.status = "failed"
        s.error_message = "boom happened"
        c.start_step(s)
        c.end_step(s)
        step = c._features[0].scenarios[0].steps[0]
        assert step.error is not None
        assert "boom happened" in step.error.message

    def test_extract_examples_from_list_and_dict(self):
        c = Collector()
        c.start_feature(self._feature())
        c.start_scenario(self._scenario(examples=[{"a": 1}, "x"]))
        sc = c._features[0].scenarios[0]
        assert sc.examples == [{"a": 1}, {"value": "x"}]

        c2 = Collector()
        c2.start_feature(self._feature())
        c2.start_scenario(self._scenario(examples={"k": "v"}))
        assert c2._features[0].scenarios[0].examples == [{"k": "v"}]

    def test_extract_example_tags_via_effective_tags(self):
        c = Collector()
        c.start_feature(self._feature())
        c.start_scenario(
            self._scenario(tags=["t1"], effective_tags=["t1", "t2", "t3"], _row=None, parent=None)
        )
        sc = c._features[0].scenarios[0]
        assert sc.example_tags == ["t2", "t3"]

    def test_sync_background_copies_statuses(self):
        bg_step = _behave_step("bg")
        behave_bg = SimpleNamespace(
            name="bg",
            keyword="Background",
            steps=[bg_step],
            all_steps=[bg_step],
            location=None,
        )
        c = Collector()
        c.start_feature(self._feature())
        c.start_scenario(self._scenario(background=behave_bg))
        s = _behave_step("main")
        c.start_step(bg_step)
        c.end_step(bg_step)
        c.start_step(s)
        c.end_step(s)
        c.end_scenario(self._scenario(background=behave_bg, all_steps=[bg_step, s]))
        sc = c._features[0].scenarios[0]
        assert sc.background is not None
        assert sc.background.steps[0].status == "passed"

    def test_duration_nanos_disabled(self):
        from behave_modern_json_report.cucumber_serializer import (
            CucumberSerializerOptions,
        )

        report = _minimal_report(
            features=[
                Feature(
                    id="f",
                    name="F",
                    scenarios=[
                        Scenario(
                            id="s",
                            name="S",
                            feature_id="f",
                            steps=[_step(duration=0.25)],
                        )
                    ],
                )
            ]
        )
        data = json.loads(
            serialize_cucumber(report, CucumberSerializerOptions(duration_in_nanos=False))
        )
        assert data[0]["elements"][0]["steps"][0]["result"]["duration"] == 0

    def test_cucumber_embedding_method(self):
        stream = io.StringIO()
        fmt = CucumberJSONFormatter(stream=stream)
        feature = SimpleNamespace(
            name="F",
            filename="f",
            keyword="Feature",
            description=[],
            tags=[],
            status="passed",
            duration=0.0,
            scenarios=[],
            rules=[],
            background=None,
            location=None,
        )
        scenario = SimpleNamespace(
            name="s",
            filename="f",
            keyword="Scenario",
            tags=[],
            status="passed",
            duration=0.0,
            steps=[],
            all_steps=[],
            background=None,
            feature=feature,
            rule=None,
            location=None,
        )
        fmt.feature(feature)
        fmt.scenario(scenario)
        s = _behave_step()
        fmt.step(s)
        fmt.embedding("text/plain", b"embedded text")
        fmt.result(s)
        fmt.eof()
        data = json.loads(stream.getvalue())
        embs = data[0]["elements"][0]["steps"][0]["embeddings"]
        assert embs[0]["mime_type"] == "text/plain"
        assert base64.b64decode(embs[0]["data"]) == b"embedded text"

    def test_cucumber_flush_to_path(self, tmp_path):
        target = tmp_path / "cuc.json"
        fmt = CucumberJSONFormatter(stream=str(target))
        fmt.eof()
        data = json.loads(target.read_text())
        assert data == []
