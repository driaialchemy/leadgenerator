"""The class page keeps what a person types, and the words on screen stay plain."""

import json
import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.paths import repo_root
from leadgen.ui_data import profile_ids
from leadgen.ui_theme import PAIRS, contrast_ratio

APP = repo_root() / "src" / "leadgen" / "app.py"
SUMMARY = "new businesses found"


def test_contrast_pairs_meet_wcag_aa():
    names = {name for name, _foreground, _background in PAIRS}
    required = {
        "banner_start",
        "banner_end",
        "step_current",
        "step_done",
        "step_ready",
        "step_locked",
        "primary",
        "primary_disabled",
        "secondary",
        "secondary_disabled",
        "chip_wait",
        "chip_ok",
        "chip_stop",
        "tile_found",
        "tile_shortlist",
        "tile_waiting",
        "tile_approved",
        "tile_sent",
        "card_find",
        "card_shortlist",
        "card_draft",
        "card_review",
        "card_send",
    }
    assert required <= names
    for name, foreground, background in PAIRS:
        assert contrast_ratio(foreground, background) >= 4.5, name


def test_industry_box_persists_across_rerun_and_tabs(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.text_input(key="industry_query").set_value("restaurants").run(timeout=60)
    assert at.text_input(key="industry_query").value == "restaurants"
    at.button(key="suggest_0").click().run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    assert SUMMARY in _text(at)
    at.run(timeout=60)
    _switch(at, "shortlist", "search")
    assert at.text_input(key="industry_query").value == "restaurants"
    assert SUMMARY in _text(at)


def test_search_results_name_businesses_and_contacts(monkeypatch, tmp_path):
    at = _searched(monkeypatch, tmp_path)
    text = _text(at)
    assert "showing 25" in text
    assert "Elden Kitchen" in text
    assert "Arizona company directory" in text
    assert at.text_input(key="industry_query").placeholder
    assert "No new businesses match" not in text


def test_a_second_search_moves_the_first_to_previous_searches(monkeypatch, tmp_path):
    at = _searched(monkeypatch, tmp_path)
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    at.button(key="nav_shortlist").click().run(timeout=60)
    _ok(at)
    assert "Elden Kitchen" in _text(at)


def test_approver_and_edit_fields_persist(monkeypatch, tmp_path):
    from test_app import _seed_draft

    _seed_draft(tmp_path)
    at = _open(monkeypatch, tmp_path)
    at.button(key="nav_run").click().run(timeout=60)
    at.button(key="run").click().run(timeout=60)
    _ok(at)
    at.text_input(key="approver").set_value("Ada").run(timeout=60)
    at.text_area(key="edit_hook").set_value("You mentioned the backlog.").run(timeout=60)
    at.text_area(key="edit_bridge").set_value("A person reviews the work before it goes out.").run(timeout=60)
    _switch(at, "outbox", "review")
    assert at.text_input(key="approver").value == "Ada"
    assert at.text_area(key="edit_hook").value == "You mentioned the backlog."
    assert at.text_area(key="edit_bridge").value == "A person reviews the work before it goes out."


def test_sidebar_has_no_picker_or_red_team(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    keys = {getattr(node, "key", None) for node in at.sidebar}
    assert "profile" not in keys
    assert "data_mode" not in keys
    assert "red_team" not in keys
    assert "Kill switch is engaged. Refusing to run." not in _text(at)
    at.button(key="nav_settings").click().run(timeout=60)
    text = _text(at)
    assert "Tailor the pitch" in text
    assert "Write the email" in text
    assert "Quality score" in text
    assert at.button(key="check_keys").label == "Check keys"
    assert "Red-team" not in text


def test_walkthrough_reaches_previous_searches(monkeypatch, tmp_path):
    at = _searched(monkeypatch, tmp_path)
    at.button(key="next_search").click().run(timeout=60)
    assert at.session_state["step"] == "shortlist"
    at.button(key="nav_run").click().run(timeout=60)
    _ok(at)
    assert at.session_state["step"] == "run"
    assert "Elden Kitchen" in _text(at)


def test_locked_steps_stay_put_and_offer_a_way_forward(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.button(key="nav_review").click().run(timeout=60)
    _ok(at)
    assert at.session_state["step"] == "search"
    assert "Nothing to review yet" in _text(at)
    assert at.button(key="unlock_review").label == "Go to Draft"
    at.button(key="unlock_review").click().run(timeout=60)
    assert at.session_state["step"] == "run"
    at.button(key="nav_outbox").click().run(timeout=60)
    _ok(at)
    assert at.session_state["step"] == "run"
    assert "Nothing sent yet" in _text(at)
    assert at.button(key="unlock_outbox").label == "Go to Review"


def test_sidebar_more_opens_the_record_pages(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    keys = {getattr(node, "key", None) for node in at.sidebar}
    assert {"nav_logbook", "nav_settings"} <= keys
    assert "check_keys" not in keys
    assert "red_team" not in keys
    at.button(key="nav_logbook").click().run(timeout=60)
    assert at.session_state["step"] == "logbook"
    assert "Logbook" in _text(at)
    at.button(key="nav_settings").click().run(timeout=60)
    assert at.session_state["step"] == "settings"
    assert "Settings" in _text(at)
    assert at.button(key="check_keys").label == "Check keys"


def test_wizard_walk_has_one_primary(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    assert _states(at)["search"] == "current"
    assert _states(at)["shortlist"] == "ready"
    assert _states(at)["run"] == "locked"
    assert _states(at)["review"] == "locked"
    assert _states(at)["outbox"] == "locked"
    assert _primaries(at) == ["Search"]

    at.text_input(key="industry_query").set_value("restaurants").run(timeout=60)
    at.button(key="suggest_0").click().run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    assert _primaries(at) == ["Next"]
    assert _tiles(at)["Businesses found"] == 25
    assert _states(at)["run"] == "ready"
    at.button(key="next_search").click().run(timeout=60)
    assert at.session_state["step"] == "shortlist"
    assert _states(at)["search"] == "done"
    assert _states(at)["shortlist"] == "current"
    at.button(key="nav_run").click().run(timeout=60)
    assert at.session_state["step"] == "run"
    assert _states(at)["shortlist"] == "done"
    assert _states(at)["run"] == "current"
    assert _states(at)["review"] == "locked"
    assert _primaries(at) == ["Run"]
    assert "Elden Kitchen" in _text(at)


def _open(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("LEADGEN_KILL_SWITCH", raising=False)
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    _ok(at)
    return at


def _searched(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.text_input(key="industry_query").set_value("restaurants").run(timeout=60)
    at.button(key="suggest_0").click().run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    return at


def _switch(at, away: str, back: str) -> None:
    at.button(key=f"nav_{away}").click().run(timeout=60)
    _ok(at)
    at.button(key=f"nav_{back}").click().run(timeout=60)
    _ok(at)


def _states(at) -> dict:
    return dict(re.findall(r'data-step="(\w+)" data-state="(\w+)"', _text(at)))


def _primaries(at) -> list[str]:
    return [button.label for button in at.button if button.proto.type == "primary"]


def _tiles(at) -> dict:
    pairs = re.findall(
        r'class="tile-value">(\d+)</span><span class="tile-label">([^<]+)',
        _text(at),
    )
    return {label: int(value) for value, label in pairs}


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
