"""The class page renders, runs, and approves without a network call."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.llm import ProviderError
from leadgen.paths import repo_root

APP = repo_root() / "src" / "leadgen" / "app.py"
SECRET = "unit-test-key-value-9f3a"
TITLES = ("Shortlist", "Run", "Review", "Outbox", "Logbook", "Funnel")


def test_no_image_is_rendered_or_shipped(monkeypatch, tmp_path):
    shipped = [
        path
        for path in (repo_root() / "assets").rglob("*")
        if path.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
    ]
    assert shipped == []
    _isolate(monkeypatch, tmp_path)
    at = _open()
    _ok(at)
    assert list(at.image) == []


def test_every_tab_renders_for_both_profiles(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    at = _open()
    _ok(at)
    _titles(at)
    other = _profile_ids()[1]
    at.selectbox(key="profile").set_value(other).run(timeout=60)
    _ok(at)
    _titles(at)


def test_run_then_approve_writes_one_outbox_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    at = _open()
    assert _model_calls(tmp_path) == 0
    at.button(key="run").click().run(timeout=60)
    _ok(at)
    text = _text(at)
    assert "Waiting for your approval" in text
    status_files = list((tmp_path / "runs").glob("*/status.json"))
    assert len(status_files) == 1
    assert json.loads(status_files[0].read_text(encoding="utf-8"))["status"] == "PENDING_APPROVAL"
    assert "Attempt 1" in text
    assert "Attempt 2" in text
    calls = _model_calls(tmp_path)
    assert calls > 0
    at.run(timeout=60)
    assert _model_calls(tmp_path) == calls
    at.text_input(key="approver").set_value("Ada").run(timeout=60)
    assert _model_calls(tmp_path) == calls
    at.button(key="approve").click().run(timeout=60)
    assert "Findings must be acknowledged." in _text(at)
    assert list((tmp_path / "outbox").glob("*.txt")) == []
    at.checkbox(key="ack").set_value(True).run(timeout=60)
    at.button(key="approve").click().run(timeout=60)
    files = list((tmp_path / "outbox").glob("*.txt"))
    assert len(files) == 1
    approval = tmp_path / "runs" / files[0].stem / "approval.json"
    assert json.loads(approval.read_text(encoding="utf-8"))["name"] == "Ada"


def test_check_keys_hides_the_key(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", SECRET)

    def boom(**kwargs):
        raise RuntimeError(f"upstream failed {kwargs.get('api_key')}")

    monkeypatch.setattr("google.genai.Client", boom)
    at = _open()
    at.button(key="check_keys").click().run(timeout=60)
    _ok(at)
    rendered = _text(at) + str(at.session_state.get("key_report", ""))
    assert SECRET not in rendered
    assert "key yes" in rendered
    assert "key no" in rendered


def test_provider_error_suggests_offline(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    def boom(*_args, **_kwargs):
        raise ProviderError("tailor", "google", "gemini-4-argon", 429, "quota exceeded")

    monkeypatch.setattr("leadgen.pipeline.run_prospect", boom)
    at = _open()
    at.button(key="run").click().run(timeout=60)
    _ok(at)
    text = _text(at)
    assert "tailor google: 429 quota exceeded" in text
    assert "switch to Offline" in text


def test_kill_switch_disables_run_and_approve(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    at = _open()
    _ok(at)
    assert at.button(key="run").disabled
    assert at.button(key="approve").disabled
    assert "Kill switch is engaged. Refusing to run." in _text(at)


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("LEADGEN_KILL_SWITCH", raising=False)
    monkeypatch.delenv("LEADGEN_DEMO_TEMPT", raising=False)


def _open():
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    return at


def _ok(at):
    assert list(at.exception) == []


def _titles(at):
    text = _text(at)
    for title in TITLES:
        assert title in text


def _text(at) -> str:
    chunks = []
    for name in (
        "markdown",
        "header",
        "subheader",
        "code",
        "error",
        "success",
        "info",
        "warning",
        "caption",
        "text",
    ):
        block = getattr(at, name, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None) or getattr(item, "label", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)


def _model_calls(root: Path) -> int:
    path = root / "runs" / "flight_recorder.jsonl"
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if json.loads(line).get("event_type") == "model_call":
            count += 1
    return count


def _profile_ids():
    folder = repo_root() / "config" / "profiles"
    return sorted(path.stem for path in folder.glob("*.yaml"))
