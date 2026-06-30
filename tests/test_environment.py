"""Tests for the environment detector."""

from __future__ import annotations

from behave_modern_json_report.environment import detect_environment


class TestDetectEnvironment:
    def test_python_version_present(self):
        env = detect_environment()
        assert env.python_version is not None
        assert "." in env.python_version

    def test_platform_present(self):
        env = detect_environment()
        assert env.platform is not None

    def test_os_present(self):
        env = detect_environment()
        assert env.os is not None

    def test_hostname_present(self):
        env = detect_environment()
        assert env.hostname is not None

    def test_behave_version_override(self):
        env = detect_environment(behave_version="1.2.6")
        assert env.behave_version == "1.2.6"

    def test_extra_merged(self):
        env = detect_environment(extra={"custom": "value"})
        assert env.extra["custom"] == "value"

    def test_ci_provider_detected(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        env = detect_environment()
        assert env.ci_provider == "github-actions"
