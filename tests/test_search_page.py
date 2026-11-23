"""The Search tab runs from an example and does not repeat itself on the next redraw."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.paths import repo_root

APP = repo_root() / "src" / "leadgen" / "app.py"


def test_search_runs_once_and_the_kill_switch_disables_search(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("LEADGEN_KILL_SWITCH", raising=False)
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    assert list(at.exception) == []
    assert "Search" in _text(at)
    at.text_input(key="industry_query").set_value("restaurants").run(timeout=60)
    at.button(key="suggest_0").click().run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    assert list(at.exception) == []
    text = _text(at)
    assert "new businesses found" in text
    assert "Named contact" in text or "Owner" in text
    searches = _count(tmp_path, "search")
    assert searches == 1
    at.run(timeout=60)
    assert _count(tmp_path, "search") == searches

    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    blocked = AppTest.from_file(str(APP))
    blocked.run(timeout=60)
    assert list(blocked.exception) == []
    assert blocked.button(key="search").disabled


def _text(at) -> str:
    chunks = []
    for name in ("markdown", "header", "info", "warning", "caption", "text"):
        block = getattr(at, name, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None) or getattr(item, "label", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)


def _count(root: Path, event_type: str) -> int:
    path = root / "runs" / "flight_recorder.jsonl"
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if json.loads(line).get("event_type") == event_type)
