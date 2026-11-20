"""The flight recorder only appends, and live mode fails before the SDK."""

import json

import pytest

from leadgen.flight_recorder import append_event, recorder_path
from leadgen.llm import ConfigError, complete
from leadgen.schemas import FlightEvent


def test_appends_do_not_rewrite_earlier_lines(tmp_path):
    path = recorder_path(tmp_path)
    append_event(_event("one"), path)
    before = path.read_bytes()
    append_event(_event("two"), path)
    after = path.read_bytes()
    assert after.startswith(before)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["detail"] for row in rows] == ["one", "two"]


def test_live_mode_without_a_key_does_not_call_the_sdk(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_LLM_MODE", "live")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("LEADGEN_MODEL", "")
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "0")

    def explode(**kwargs):
        raise AssertionError("SDK client was constructed")

    monkeypatch.setattr("leadgen.llm.anthropic.Anthropic", explode)
    with pytest.raises(ConfigError):
        complete("tailor", "Hello", "sample", "P-1", 1, tmp_path)


def _event(detail: str) -> FlightEvent:
    return FlightEvent(
        event_id="evt-" + detail,
        ts="2026-11-19T00:00:00+00:00",
        run_id="run",
        event_type="model_call",
        actor="tailor",
        mode="offline",
        status="ok",
        detail=detail,
    )
