"""The class page keeps what a person types, and the words on screen stay plain."""

import json
import re
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


def test_search_box_persists_across_rerun_and_tabs(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    at.text_input(key="search_query").set_value("Registered firms in Phoenix").run(timeout=60)
    assert at.text_input(key="search_query").value == "Registered firms in Phoenix"
    at.button(key="search").click().run(timeout=60)
    _ok(at)
    assert "7 matches, 3 named contacts, 6 shown, 1 held back" in _text(at)
    at.run(timeout=60)
    _switch(at, "shortlist", "search")
    assert at.text_input(key="search_query").value == "Registered firms in Phoenix"
    assert "7 matches, 3 named contacts, 6 shown, 1 held back" in _text(at)


def test_example_fills_the_box_and_returns_results(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    example = at.button(key="example_0").label
    at.button(key="example_0").click().run(timeout=60)
    _ok(at)
    assert at.text_input(key="search_query").value == example
    assert example == "Restaurants in Phoenix"
    assert "7 matches, 3 named contacts, 6 shown, 1 held back" in _text(at)
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
    assert at.text_input(key="field_location").value == "Tucson"

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_contact", "Named contact")
    text = _text(at)
    assert "7 matches, 3 named contacts, 6 shown, 1 held back" in text
    assert "Northwind Example LLC" in text
    assert "Old Registration LLC" in text
    assert "Quiet Mail LLC" not in text

    at.button(key="example_0").click().run(timeout=60)
    _set_field(at, "field_max", "1")
    text = _text(at)
    assert "7 matches, 3 named contacts, 6 shown, 1 held back" in text
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


def test_walkthrough_reaches_the_shortlist(monkeypatch, tmp_path):
    root = tmp_path / "acme"
    root.mkdir()
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(root))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    _ok(at)
    example = at.button(key="example_0").label
    at.button(key="example_0").click().run(timeout=60)
    _ok(at)
    assert at.text_input(key="search_query").value == example
    at.button(key="add_all").click().run(timeout=60)
    _ok(at)
    at.button(key="next_search").click().run(timeout=60)
    assert at.session_state["step"] == "shortlist"
    assert "Northwind Example LLC" in _text(at) or "Congress Kitchen" in _text(at)


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
    assert {"nav_logbook", "nav_funnel", "nav_settings"} <= keys
    assert "check_keys" not in keys
    assert "red_team" not in keys
    at.button(key="nav_logbook").click().run(timeout=60)
    assert at.session_state["step"] == "logbook"
    assert "Logbook" in _text(at)
    at.button(key="nav_funnel").click().run(timeout=60)
    assert at.session_state["step"] == "funnel"
    assert "Funnel" in _text(at)
    at.button(key="nav_settings").click().run(timeout=60)
    assert at.session_state["step"] == "settings"
    assert "Settings" in _text(at)
    assert at.button(key="check_keys").label == "Check keys"


def test_wizard_walk_has_one_primary_and_the_b2b_counts(monkeypatch, tmp_path):
    at = _open(monkeypatch, tmp_path)
    assert _states(at)["search"] == "current"
    assert _states(at)["shortlist"] == "ready"
    assert _states(at)["run"] == "locked"
    assert _states(at)["review"] == "locked"
    assert _states(at)["outbox"] == "locked"
    assert _primaries(at) == ["Search"]

    at.button(key="example_0").click().run(timeout=60)
    _ok(at)
    assert _primaries(at) == ["Next"]
    assert _tiles(at) == {
        "Businesses found": 6,
        "On shortlist": 0,
        "Drafts waiting": 0,
        "Approved": 0,
        "Sent": 0,
    }
    at.button(key="add_all").click().run(timeout=60)
    _ok(at)
    at.button(key="next_search").click().run(timeout=60)
    assert at.session_state["step"] == "shortlist"
    assert _states(at)["search"] == "done"
    assert _states(at)["shortlist"] == "current"
    assert _primaries(at) == ["Next"]

    at.button(key="next_shortlist").click().run(timeout=60)
    assert at.session_state["step"] == "run"
    assert _states(at)["shortlist"] == "done"
    assert _states(at)["run"] == "current"
    assert _states(at)["review"] == "locked"
    assert _primaries(at) == ["Run"]

    assert "Northwind Example LLC" in _text(at) or "Congress Kitchen" in _text(at)


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
