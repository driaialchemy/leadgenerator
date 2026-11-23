"""Streamlit Community Cloud: settings order, folders, and the copy / mailto send step."""

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from streamlit.testing.v1 import AppTest

from leadgen import cloud
from leadgen.paths import repo_root

APP = repo_root() / "src" / "leadgen" / "app.py"


def test_cloud_flag_overrides_the_path_check(monkeypatch):
    monkeypatch.setenv("LEADGEN_CLOUD", "1")
    assert cloud.is_cloud()
    monkeypatch.setenv("LEADGEN_CLOUD", "0")
    assert not cloud.is_cloud()
    monkeypatch.delenv("LEADGEN_CLOUD")
    assert not cloud.is_cloud()  # this checkout is not under /mount/src/
    monkeypatch.setattr(cloud, "repo_root", lambda: Path("/mount/src/leadgenerator"))
    assert cloud.is_cloud()


def test_environment_beats_secrets_and_secrets_beat_nothing(monkeypatch):
    class Secrets(dict):
        pass

    secrets = Secrets({"GOOGLE_API_KEY": "from-secrets-123", "ANTHROPIC_API_KEY": "from-secrets-456", "OTHER": "x"})
    monkeypatch.delenv("LEADGEN_SKIP_SECRETS")
    monkeypatch.setenv("GOOGLE_API_KEY", "from-env-000")
    monkeypatch.setattr("streamlit.secrets", secrets, raising=False)
    cloud.load_streamlit_secrets()
    assert os.environ["GOOGLE_API_KEY"] == "from-env-000"
    assert os.environ["ANTHROPIC_API_KEY"] == "from-secrets-456"
    assert "OTHER" not in os.environ
    monkeypatch.delenv("ANTHROPIC_API_KEY")


def test_missing_secrets_and_a_missing_key_file_do_not_error(monkeypatch, tmp_path):
    class Broken:
        def get(self, *_args):
            raise FileNotFoundError("no secrets.toml")

    monkeypatch.delenv("LEADGEN_SKIP_SECRETS")
    monkeypatch.setattr("streamlit.secrets", Broken(), raising=False)
    monkeypatch.setenv("LEADGEN_ENV_FILE", str(tmp_path / "missing.env"))
    from leadgen.llm import load_project_env

    load_project_env()


def test_cloud_creates_runs_and_outbox_and_defaults_to_live(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_CLOUD", "1")
    monkeypatch.delenv("LEADGEN_LLM_MODE")
    cloud.prepare_cloud(tmp_path)
    assert (tmp_path / "runs").is_dir() and (tmp_path / "outbox").is_dir()
    assert os.environ["LEADGEN_LLM_MODE"] == "live"
    monkeypatch.delenv("LEADGEN_LLM_MODE")


def test_mailto_encodes_recipient_subject_and_body():
    url = cloud.mailto_url("riley@example.com", "Hi & welcome", "Line one\nLine 2: 100% sure?")
    parts = urlparse(url)
    assert parts.scheme == "mailto" and unquote(parts.path) == "riley@example.com"
    query = parse_qs(parts.query)
    assert query["subject"] == ["Hi & welcome"]
    assert query["body"] == ["Line one\nLine 2: 100% sure?"]
    assert " " not in url and "\n" not in url


def test_clipboard_html_cannot_be_broken_by_the_text():
    html = cloud.clipboard_html('</script><b>"quoted"</b>', "b", "f", "i", "n")
    assert html.count("</script>") == 1


def test_cloud_page_shows_the_note_and_hides_gmail_and_outlook(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_CLOUD", "1")
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    assert list(at.exception) == []
    assert cloud.SHARED_NOTE in [item.value for item in at.caption]
    assert (tmp_path / "runs").is_dir() and (tmp_path / "outbox").is_dir()
    at.button(key="nav_settings").click().run(timeout=60)
    keys = {getattr(node, "key", None) for node in at.button}
    assert not {"connect_gmail", "connect_outlook", "disconnect_gmail", "disconnect_outlook"} & keys


def test_local_page_keeps_mail_connections_and_has_no_shared_note(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    assert cloud.SHARED_NOTE not in [item.value for item in at.caption]
    at.button(key="nav_settings").click().run(timeout=60)
    keys = {getattr(node, "key", None) for node in at.button}
    assert {"connect_gmail", "connect_outlook"} <= keys


def test_cloud_send_step_offers_copy_and_mailto_instead_of_mail(monkeypatch, tmp_path):
    from test_app import _seed_draft

    monkeypatch.setenv("LEADGEN_CLOUD", "1")
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    _seed_draft(tmp_path)
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    at.button(key="nav_run").click().run(timeout=60)
    at.button(key="run").click().run(timeout=60)
    assert list(at.exception) == []
    at.text_input(key="approver").set_value("Ada").run(timeout=60)
    at.checkbox(key="ack").set_value(True).run(timeout=60)
    at.button(key="approve").click().run(timeout=60)
    at.button(key="nav_outbox").click().run(timeout=60)
    assert list(at.exception) == []
    keys = {getattr(node, "key", None) for node in at.button}
    assert not {"save_draft", "confirm_send", "reconnect_mail"} & keys
    assert not {"mail_destination", "mail_action"} & {getattr(node, "key", None) for node in at.radio}
    link = [node for node in at.get("link_button")]
    assert link, "Open in my email app is missing"
    assert link[0].proto.url.startswith("mailto:riley@example.com?subject=")
