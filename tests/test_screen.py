"""The class page keeps what a person types, and the words on screen stay plain."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.paths import repo_root
from leadgen.ui_data import profile_ids
from leadgen.ui_theme import PAIRS, contrast_ratio

APP = repo_root() / "src" / "leadgen" / "app.py"
FIELDS = (
    "field_kind",
    "field_location",
    "field_from",
    "field_to",
    "field_business",
    "field_contact",
    "field_max",
)
SHOWN = ("Northwind Example LLC", "Old Registration LLC", "Quiet Mail LLC")


def test_contrast_pairs_meet_wcag_aa():
    for name, foreground, background in PAIRS:
        assert contrast_ratio(foreground, background) >= 4.5, name


def test_search_box_persists_across_rerun_and_tabs(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.text_input(key="search_query").set_value("Registered firms in Phoenix").run(timeout=60)
    assert at.text_input(key="search_query").value == "Registered firms in Phoenix"
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    assert "4 matches, 2 named contacts, 3 shown, 1 held back" in _text(at)
    at.run(timeout=60)
    _switch(at, "shortlist", "search")
    assert at.text_input(key="search_query").value == "Registered firms in Phoenix"
    assert "4 matches, 2 named contacts, 3 shown, 1 held back" in _text(at)


def test_example_fills_the_box_and_returns_results(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    example = at.button(key="example_0").label
    at.button(key="example_0").click().run(timeout=60)
    _ok(at)
    assert at.text_input(key="search_query").value == example
    assert example == "Registered firms in Phoenix"
    assert "4 matches, 2 named contacts, 3 shown, 1 held back" in _text(at)
    assert "Named contact" in _text(at)


def test_every_search_field_has_placeholder_and_help(monkeypatch, tmp_path):
    at = _searched(monkeypatch, tmp_path)
    request = at.text_input(key="search_query")
    assert request.placeholder
    assert request.help
    for key in FIELDS:
        field = at.text_input(key=key)
        assert field.placeholder, key
        assert field.help, key


def test_update_results_uses_the_edited_fields(monkeypatch, tmp_path):
    at = _searched(monkeypatch, tmp_path)
    _set_field(at, "field_location", "Tucson")
    text = _text(at)
    assert "Tucson Example LLC" in text
    assert "Northwind Example LLC" not in text
    assert "1 matches, 1 named contacts, 1 shown, 0 held back" in text
    assert at.text_input(key="field_location").value == "Tucson"

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_kind", "999999")
    text = _text(at)
    assert "0 matches, 0 named contacts, 0 shown, 0 held back" in text
    assert "Northwind Example LLC" not in text

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_business", "Nonprofit")
    text = _text(at)
    assert "0 matches, 0 named contacts, 0 shown, 0 held back" in text
    assert "Northwind Example LLC" not in text

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_contact", "Named contact")
    text = _text(at)
    assert "4 matches, 2 named contacts, 3 shown, 1 held back" in text
    assert "Northwind Example LLC" in text
    assert "Old Registration LLC" in text
    assert "Quiet Mail LLC" not in text

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_max", "1")
    text = _text(at)
    assert "4 matches, 2 named contacts, 3 shown, 1 held back" in text
    present = [name for name in SHOWN if name in text]
    assert present == ["Northwind Example LLC"]

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_from", "May 24")
    assert "Use a date like 2026-05-24." in _text(at)
    assert "Northwind Example LLC" in _text(at)
    _set_field(at, "field_to", "11/20/2026")
    assert "Use a date like 2026-05-24." in _text(at)
    _set_field(at, "field_from", "2026-05-24")
    _set_field(at, "field_to", "2026-11-20")
    text = _text(at)
    assert "Use a date like 2026-05-24." not in text
    assert "Northwind Example LLC" in text
    assert at.text_input(key="field_from").value == "2026-05-24"
    assert at.text_input(key="field_to").value == "2026-11-20"


def test_profile_and_data_mode_persist(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    assert "B2B-001" in _text(at)
    at.selectbox(key="profile").set_value("home_services").run(timeout=60)
    _ok(at)
    assert at.selectbox(key="profile").value == "home_services"
    assert "HOME-001" in _text(at)
    assert "B2B-001" not in _text(at)
    _switch(at, "funnel", "shortlist")
    assert at.selectbox(key="profile").value == "home_services"
    assert "HOME-001" in _text(at)

    at.radio(key="data_mode").set_value("Live").run(timeout=60)
    assert at.radio(key="data_mode").value == "Live"
    assert "Data mode: Live" in _text(at)
    _switch(at, "settings", "shortlist")
    assert at.radio(key="data_mode").value == "Live"
    at.radio(key="data_mode").set_value("Practice data").run(timeout=60)
    assert at.radio(key="data_mode").value == "Practice data"
    assert "Data mode: Practice data" in _text(at)


def test_approver_and_edit_fields_persist(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.button(key="run").click().run(timeout=60)
    _ok(at)
    at.text_input(key="approver").set_value("Ada").run(timeout=60)
    at.text_area(key="edit_hook").set_value("You mentioned the backlog.").run(timeout=60)
    at.text_area(key="edit_bridge").set_value("A person reviews the work before it goes out.").run(timeout=60)
    _switch(at, "outbox", "review")
    assert at.text_input(key="approver").value == "Ada"
    assert at.text_area(key="edit_hook").value == "You mentioned the backlog."
    assert at.text_area(key="edit_bridge").value == "A person reviews the work before it goes out."


def test_sidebar_holds_profile_and_data_mode(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    keys = {getattr(node, "key", None) for node in at.sidebar}
    assert "profile" in keys
    assert "data_mode" in keys
    assert "check_keys" not in keys
    assert "red_team" not in keys
    assert "Kill switch is engaged. Refusing to run." not in _text(at)
    text = _text(at)
    assert "Tailor the pitch" in text
    assert "Write the email" in text
    assert "Quality score" in text
    assert at.button(key="check_keys").label == "Check keys"
    assert at.checkbox(key="red_team").label == "Red-team toggle"


def test_walkthrough_reaches_one_outbox_file(monkeypatch, tmp_path):
    for profile_id in profile_ids():
        root = tmp_path / profile_id
        root.mkdir()
        monkeypatch.setenv("LEADGEN_DATA_ROOT", str(root))
        at = AppTest.from_file(str(APP))
        at.run(timeout=60)
        _ok(at)
        if at.selectbox(key="profile").value != profile_id:
            at.selectbox(key="profile").set_value(profile_id).run(timeout=60)
            _ok(at)
        example = at.button(key="example_0").label
        at.button(key="example_0").click().run(timeout=60)
        _ok(at)
        assert at.text_input(key="search_query").value == example
        added = [button for button in at.button if str(button.key).startswith("add_")]
        if added:
            added[0].click().run(timeout=60)
            _ok(at)
            at.button(key="next_search").click().run(timeout=60)
        else:
            assert "No matches yet" in _text(at)
            at.button(key="nav_shortlist").click().run(timeout=60)
        assert at.session_state["step"] == "shortlist"
        at.button(key="next_shortlist").click().run(timeout=60)
        assert at.session_state["step"] == "run"
        at.button(key="run").click().run(timeout=60)
        _ok(at)
        text = _text(at)
        assert "Waiting for your approval" in text
        assert "1. Tailor the pitch: done" in text
        assert "PENDING_APPROVAL" not in text
        assert profile_id not in text
        if profile_id == "b2b_services":
            assert "Problem found:" in text
            assert "Trying again (Attempt 2)." in text
            assert "gemini-4-argon" in text
        at.button(key="next_run").click().run(timeout=60)
        at.text_input(key="approver").set_value("Ada").run(timeout=60)
        at.checkbox(key="ack").set_value(True).run(timeout=60)
        at.button(key="approve").click().run(timeout=60)
        _ok(at)
        files = list((root / "outbox").glob("*.txt"))
        assert len(files) == 1, profile_id
        approval = root / "runs" / files[0].stem / "approval.json"
        assert json.loads(approval.read_text(encoding="utf-8"))["name"] == "Ada"
        at.button(key="next_review").click().run(timeout=60)
        assert at.session_state["step"] == "outbox"
        assert "Approved by Ada" in _text(at)


def _open(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("LEADGEN_KILL_SWITCH", raising=False)
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    _ok(at)
    return at


def _searched(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.button(key="example_0").click().run(timeout=60)
    _ok(at)
    return at


def _set_field(at, key: str, value: str) -> None:
    at.text_input(key=key).set_value(value).run(timeout=60)
    assert at.text_input(key=key).value == value
    at.button(key="update_results").click().run(timeout=60)
    _ok(at)
    at.run(timeout=60)
    _switch(at, "run", "search")
    assert at.text_input(key=key).value == value


def _switch(at, away: str, back: str) -> None:
    at.button(key=f"nav_{away}").click().run(timeout=60)
    _ok(at)
    at.button(key=f"nav_{back}").click().run(timeout=60)
    _ok(at)


def _ok(at) -> None:
    assert list(at.exception) == [], list(at.exception)


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
