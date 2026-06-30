"""Tests for the high-level attachment helpers."""

from __future__ import annotations

from behave_modern_json_report import attach


class FakeFormatter:
    """Minimal fake formatter with add_attachment / add_log."""

    def __init__(self) -> None:
        self.attachments: list[dict] = []
        self.logs: list[dict] = []

    def add_attachment(self, **kwargs) -> None:
        self.attachments.append(kwargs)

    def add_log(self, *, level: str, message: str) -> None:
        self.logs.append({"level": level, "message": message})


class FakeContext:
    """Minimal fake Behave context with a _runner.formatters list."""

    def __init__(self, formatter: FakeFormatter | None = None) -> None:
        self._runner = type("R", (), {"formatters": [formatter] if formatter else []})()


class TestFindFormatter:
    def test_none_context(self):
        assert attach._find_formatter(None) is None

    def test_no_runner(self):
        ctx = type("C", (), {})()
        assert attach._find_formatter(ctx) is None

    def test_no_formatters(self):
        ctx = FakeContext(None)
        assert attach._find_formatter(ctx) is None

    def test_finds_formatter(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        assert attach._find_formatter(ctx) is fmt


class TestAttachText:
    def test_attach_text(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        attach.attach_text(ctx, "hello world")
        assert len(fmt.attachments) == 1
        assert fmt.attachments[0]["name"] == "note.txt"
        assert fmt.attachments[0]["content"] == "hello world"
        assert fmt.attachments[0]["encoding"] == "raw"

    def test_no_formatter_silently_returns(self):
        ctx = FakeContext(None)
        attach.attach_text(ctx, "hello")  # should not raise


class TestAttachJson:
    def test_attach_json(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        attach.attach_json(ctx, {"key": "value"})
        assert len(fmt.attachments) == 1
        assert fmt.attachments[0]["mime_type"] == "application/json"
        assert '"key"' in fmt.attachments[0]["content"]


class TestAttachScreenshot:
    def test_attach_bytes(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        attach.attach_screenshot(ctx, b"\x89PNG fake data")
        assert len(fmt.attachments) == 1
        assert fmt.attachments[0]["mime_type"] == "image/png"
        assert fmt.attachments[0]["encoding"] == "base64"

    def test_no_formatter_silently_returns(self):
        ctx = FakeContext(None)
        attach.attach_screenshot(ctx, b"data")  # should not raise


class TestLog:
    def test_log_message(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        attach.log(ctx, "something happened")
        assert len(fmt.logs) == 1
        assert fmt.logs[0]["message"] == "something happened"
        assert fmt.logs[0]["level"] == "INFO"

    def test_log_with_level(self):
        fmt = FakeFormatter()
        ctx = FakeContext(fmt)
        attach.log(ctx, "error!", level="ERROR")
        assert fmt.logs[0]["level"] == "ERROR"
