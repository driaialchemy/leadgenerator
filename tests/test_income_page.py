"""Each new profile renders on every tab."""

from streamlit.testing.v1 import AppTest

from leadgen.paths import repo_root

APP = repo_root() / "src" / "leadgen" / "app.py"
TITLES = ("Find", "Shortlist", "Draft", "Review", "Send", "Logbook", "Funnel")
PROFILES = {
    "ai_automation_services": "AUTO-001",
    "admin_assist_services": "ADMN-001",
    "newsletter_sponsorships": "NEWS-001",
}


def test_each_new_profile_renders_on_every_tab(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("LEADGEN_KILL_SWITCH", raising=False)
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    assert list(at.exception) == []
    for profile_id, prospect_id in PROFILES.items():
        at.selectbox(key="profile").set_value(profile_id).run(timeout=60)
        assert list(at.exception) == []
        text = _text(at)
        for title in TITLES:
            assert title in text
        assert prospect_id in text


def _text(at) -> str:
    chunks = []
    for name in ("markdown", "header", "subheader", "info", "caption", "text"):
        block = getattr(at, name, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None) or getattr(item, "label", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)
