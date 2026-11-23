"""The class page renders, runs, and approves without a network call."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.llm import ProviderError
from leadgen.paths import repo_root

APP = repo_root() / "src" / "leadgen" / "app.py"
SECRET = "unit-test-key-value-9f3a"
TITLES = ("Previous Searches", "Draft", "Review", "Send", "Logbook")
SHIPPED = {"hero_banner_web.jpg", "show_approve.jpg", "show_draft.jpg", "show_find.jpg"}


def test_only_the_named_images_ship_and_none_is_rendered_inline(monkeypatch, tmp_path):
    shipped = [
        path
        for path in (repo_root() / "assets").rglob("*")
        if path.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg"}
    ]
    # assets/source holds the originals and is git-ignored.
    assert {path.name for path in shipped if "source" not in path.parts} == SHIPPED
    _isolate(monkeypatch, tmp_path)
    at = _open()
    _ok(at)
    assert list(at.get("imgs")) == []


def test_every_tab_renders(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    at = _open()
    _ok(at)
    _titles(at)
    assert _profile_ids() == ["acme_plumbing"]


def test_run_then_approve_writes_one_outbox_file(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_draft(tmp_path)
    at = _open()
    at.button(key="nav_run").click().run(timeout=60)
    assert _model_calls(tmp_path) == 0
    at.button(key="run").click().run(timeout=60)
    _ok(at)
    text = _text(at)
    assert "Waiting for your approval" in text
    status_files = list((tmp_path / "runs").glob("*/status.json"))
    assert len(status_files) == 1
    assert json.loads(status_files[0].read_text(encoding="utf-8"))["status"] == "PENDING_APPROVAL"
    assert "Attempt 1" in text
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
    rendered = _text(at) + str(at.session_state["key_report"])
    assert SECRET not in rendered
    assert "key yes" in rendered
    assert "key no" in rendered


def test_provider_error_suggests_offline(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    _seed_draft(tmp_path)

    def boom(*_args, **_kwargs):
        raise ProviderError("tailor", "google", "gemini-4-argon", 429, "quota exceeded")

    monkeypatch.setattr("leadgen.pipeline.run_prospect", boom)
    at = _open()
    at.button(key="nav_run").click().run(timeout=60)
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


def _seed_draft(root: Path) -> None:
    prospect = {
        "prospect_id": "SAM-RIVER",
        "profile_id": "acme_plumbing",
        "contact_name": "Riley Chen",
        "organization": "Congress Kitchen",
        "email": "riley@example.com",
        "region": "Tucson",
        "source": "sam",
        "last_engaged_days": 10,
        "consent_status": "existing_relationship",
        "do_not_contact": False,
        "notes": "Asked for a walkthrough and a quote for the line.",
        "attributes": {
            "in_service_area": "yes",
            "named_contact": "yes",
            "target_industry_match": "yes",
        },
    }
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "current_search.json").write_text(
        json.dumps(
            [
                {
                    "profile_id": "acme_plumbing",
                    "prospect_id": "SAM-RIVER",
                    "prospect": prospect,
                    "business": "Congress Kitchen",
                    "city": "Tucson",
                    "industry": "",
                    "contact_name": "Riley Chen",
                    "contact_title": "",
                    "channels": "",
                    "score": 100,
                    "fit": "Hot",
                }
            ]
        ),
        encoding="utf-8",
    )
    replay = root / "sample_data" / "replays" / "acme_plumbing" / "SAM-RIVER"
    replay.mkdir(parents=True)
    (replay / "tailor.json").write_text(
        json.dumps(
            {
                "prospect_id": "SAM-RIVER",
                "claim_ids": ["GENERAL-01"],
                "evidence": [{"claim_id": "GENERAL-01", "quote": "Asked for a walkthrough"}],
            }
        ),
        encoding="utf-8",
    )
    (replay / "drafter.json").write_text(
        json.dumps(
            {
                "prospect_id": "SAM-RIVER",
                "subject_id": "SUB-01",
                "claim_ids": ["GENERAL-01"],
                "hook": "You asked for a walkthrough of the line.",
                "bridge": "We can set a time to walk the property.",
            }
        ),
        encoding="utf-8",
    )
    (replay / "evaluator.json").write_text(
        json.dumps(
            {
                "relevance": 5,
                "specificity": 5,
                "clarity": 5,
                "tone": 5,
                "suggestions": ["Keep the note this short."],
            }
        ),
        encoding="utf-8",
    )


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
