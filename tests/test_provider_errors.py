"""Vendor failures print one line and never a traceback."""

import json

import pytest

from leadgen.check_keys import main as check_keys
from leadgen.run import main as run_main

SECRET = "unit-test-key-value-9f3a"


@pytest.mark.parametrize(
    ("status", "message", "snippet"),
    [
        (
            429,
            "quota exceeded:\nfree tier limit 0 for gemini-4-argon",
            "429 quota exceeded: free tier limit 0 for gemini-4-argon",
        ),
        (401, "authentication failed", "401 authentication failed"),
        (404, "model not found", "404 model not found"),
        ("timeout", "Request timed out", "timeout Request timed out"),
    ],
)
def test_provider_error_is_one_line(monkeypatch, tmp_path, capsys, status, message, snippet):
    monkeypatch.setenv("LEADGEN_LLM_MODE", "live")
    monkeypatch.setenv("GOOGLE_API_KEY", SECRET)
    monkeypatch.setattr("google.genai.Client", _client(_failure(status, message)))

    assert check_keys() == 1
    report = capsys.readouterr().out
    google = next(line for line in report.splitlines() if line.startswith("google:"))
    assert google == f"google: key yes, call fail: {snippet}"
    assert SECRET not in report
    assert "Traceback" not in report

    code = run_main(["--profile", "b2b_services", "--prospect", "B2B-004"], root=tmp_path)
    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.splitlines() == [
        f"tailor google: {snippet}. switch to Offline or fix the account"
    ]
    assert SECRET not in captured.out
    events = [
        json.loads(line)
        for line in (tmp_path / "runs" / "flight_recorder.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    errors = [item for item in events if item["event_type"] == "error"]
    assert len(errors) == 1
    assert errors[0]["actor"] == "tailor"
    assert errors[0]["provider"] == "google"
    assert errors[0]["detail"] == snippet
    assert SECRET not in json.dumps(events)


def _failure(status, message):
    text = f"{message} {SECRET}"
    if status == "timeout":

        class APITimeoutError(Exception):
            def __init__(self):
                self.message = text
                super().__init__(text)

        return APITimeoutError()

    class APIStatusError(Exception):
        def __init__(self):
            self.status_code = status
            self.message = text
            super().__init__(text)

    return APIStatusError()


def _client(exc):
    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def generate_content(self, model, contents):
            raise exc

    return Client
