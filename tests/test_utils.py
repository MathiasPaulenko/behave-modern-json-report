"""Unit tests for utility helpers."""

from __future__ import annotations

from behave_modern_json_report import utils


class TestGenerateId:
    def test_returns_non_empty_string(self):
        assert utils.generate_id()

    def test_prefix_is_applied(self):
        uid = utils.generate_id("feature")
        assert uid.startswith("feature-")

    def test_uniqueness(self):
        ids = {utils.generate_id() for _ in range(1000)}
        assert len(ids) == 1000


class TestNowIso:
    def test_ends_with_z(self):
        assert utils.now_iso().endswith("Z")


class TestSafeTags:
    def test_none_returns_empty(self):
        assert utils.safe_tags(None) == []

    def test_dedup_and_strip(self):
        assert utils.safe_tags(["  @a ", "@a", " @b "]) == ["@a", "@b"]

    def test_string_input(self):
        assert utils.safe_tags("@smoke") == ["@smoke"]


class TestCIProvider:
    def test_none_when_no_env(self, monkeypatch):
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
            "CI",
            "CI_NAME",
        ):
            monkeypatch.delenv(key, raising=False)
        assert utils.ci_provider() is None

    def test_github_actions(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert utils.ci_provider() == "github-actions"


class TestMergeDicts:
    def test_extra_wins(self):
        assert utils.merge_dicts({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3}

    def test_none_extra(self):
        assert utils.merge_dicts({"a": 1}, None) == {"a": 1}


class TestNormalizeStatus:
    def test_none_returns_untested(self):
        assert utils.normalize_status(None) == utils.STATUS_UNTESTED

    def test_string_status(self):
        assert utils.normalize_status("passed") == "passed"
        assert utils.normalize_status("FAILED") == "failed"

    def test_enum_like(self):
        class FakeStatus:
            name = "skipped"

        assert utils.normalize_status(FakeStatus()) == "skipped"

    def test_unknown_returns_untested(self):
        assert utils.normalize_status("bogus") == utils.STATUS_UNTESTED


class TestFormatDuration:
    def test_none(self):
        assert utils.format_duration(None) == "0ms"

    def test_milliseconds(self):
        assert utils.format_duration(0.05) == "50ms"

    def test_seconds(self):
        assert utils.format_duration(2.5) == "2.50s"

    def test_minutes(self):
        assert utils.format_duration(125.0) == "2m 5s"

    def test_hours(self):
        assert utils.format_duration(3725.0) == "1h 2m 5s"


class TestGuessMime:
    def test_json(self):
        assert utils.guess_mime("data.json") == "application/json"

    def test_unknown_returns_octet_stream(self):
        assert utils.guess_mime("file.unknownext") == "application/octet-stream"


class TestStatusConstants:
    def test_all_statuses_contains_known(self):
        assert "passed" in utils.ALL_STATUSES
        assert "xfailed" in utils.ALL_STATUSES
        assert "hook_error" in utils.ALL_STATUSES

    def test_failed_statuses_includes_error_variants(self):
        assert "failed" in utils._FAILED_STATUSES
        assert "error" in utils._FAILED_STATUSES
        assert "hook_error" in utils._FAILED_STATUSES
        assert "passed" not in utils._FAILED_STATUSES
