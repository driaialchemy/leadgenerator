"""Mailbox draft and send stay behind approval. Providers here are fakes."""

import ast
import json
import secrets
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from leadgen.mail import (
    GMAIL_SCOPES,
    GRAPH_SCOPES,
    MailUnavailable,
    ProviderRejected,
    SignInExpired,
    connection_status,
    deliver,
    disconnect_account,
    reset_session_sends,
)
from leadgen.paths import repo_root
from leadgen.profiles import load_pipeline_config, load_profile

APP = repo_root() / "src" / "leadgen" / "app.py"


@pytest.fixture(autouse=True)
def _fresh_send_count():
    reset_session_sends()
    yield
    reset_session_sends()


class FakeMailbox:
    def __init__(self, account="owner@example.com", error=None, blank_id=False):
        self.account = account
        self.error = error
        self.blank_id = blank_id
        self.calls = []
        self.token = ""
        self.client_secret = ""

    def draft(self, recipient, subject, body, account):
        self.calls.append(("draft", recipient, subject, body, account))
        if self.error:
            raise self.error
        if self.blank_id:
            return ""
        return "draft-1"

    def send(self, recipient, subject, body, account):
        self.calls.append(("send", recipient, subject, body, account))
        if self.error:
            raise self.error
        if self.blank_id:
            return ""
        return "sent-1"


def test_scopes_are_the_narrow_set():
    assert GMAIL_SCOPES == ("https://www.googleapis.com/auth/gmail.compose",)
    assert GRAPH_SCOPES == (
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/Mail.ReadWrite",
    )
    source = (repo_root() / "src" / "leadgen" / "mail.py").read_text(encoding="utf-8")
    assert "gmail.readonly" not in source
    assert "gmail.modify" not in source
    assert "messages.list" not in source
    assert "smtplib" not in source


def test_draft_and_send_record_the_provider_id(tmp_path):
    run, profile, subject, body = _note(tmp_path)
    client = FakeMailbox(account="owner@example.com")
    drafted = deliver(tmp_path, run, "gmail", "draft", client=client)
    assert drafted.ok
    assert drafted.message_id == "draft-1"
    sent = deliver(
        tmp_path,
        run,
        "outlook",
        "send",
        True,
        demo_safety=False,
        client=client,
    )
    assert sent.ok
    assert sent.message_id == "sent-1"
    assert client.calls[0] == ("draft", "owner@example.com", subject, body, "owner@example.com")
    assert client.calls[1][0] == "send"
    assert client.calls[1][1:] == ("owner@example.com", subject, body, "owner@example.com")
    for part in (
        profile.sender.name,
        profile.sender.company,
        profile.sender.postal_address,
        profile.opt_out_line,
    ):
        assert part in body
    saved = json.loads((run / "mail.json").read_text(encoding="utf-8"))
    assert saved["approver"] == "Ada"
    assert saved["approved_at"]
    assert saved["last_draft"]["message_id"] == "draft-1"
    assert saved["confirmed_send"]["message_id"] == "sent-1"
    assert saved["confirmed_send"]["account"] == "owner@example.com"
    events = _events(tmp_path)
    draft_event = next(item for item in events if item["event_type"] == "mail_draft" and item["status"] == "ok")
    send_event = next(item for item in events if item["event_type"] == "mail_send" and item["status"] == "ok")
    assert draft_event["destination"] == "gmail"
    assert draft_event["recipient"] == "owner@example.com"
    assert draft_event["approver"] == "Ada"
    assert draft_event["detail"] == "drafted"
    assert send_event["message_id"] == "sent-1"
    assert send_event["detail"] == "sent"
    blob = (tmp_path / "runs" / "flight_recorder.jsonl").read_text(encoding="utf-8")
    assert "UNIQUE-BODY-SENTINEL" not in blob


def test_unapproved_note_cannot_be_drafted_or_sent(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path, approved=False)
    client = FakeMailbox()
    drafted = deliver(tmp_path, run, "gmail", "draft", client=client)
    sent = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert drafted.message == "This note has not been approved, so it cannot be drafted or sent."
    assert sent.message == drafted.message
    assert client.calls == []
    (run / "approval.json").write_text(
        json.dumps(
            {
                "decision": "REJECTED",
                "name": "Ada",
                "ack_findings": False,
                "run_id": run.name,
            }
        ),
        encoding="utf-8",
    )
    again = deliver(tmp_path, run, "gmail", "draft", client=client)
    assert again.ok is False
    assert client.calls == []


def test_demo_safety_blocks_send_and_allows_a_draft(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path, email="stranger@elsewhere.test")
    client = FakeMailbox(account="owner@example.com")
    blocked = deliver(tmp_path, run, "gmail", "send", True, demo_safety=True, client=client)
    assert blocked.ok is False
    assert "allowlist" in blocked.message
    assert client.calls == []
    drafted = deliver(tmp_path, run, "gmail", "draft", demo_safety=True, client=client)
    assert drafted.ok
    assert drafted.message_id == "draft-1"
    assert client.calls[0][0] == "draft"
    allowed = load_pipeline_config().model_copy(update={"allowlist": ["stranger@elsewhere.test"]})
    sent = deliver(
        tmp_path,
        run,
        "gmail",
        "send",
        True,
        demo_safety=True,
        client=client,
        config=allowed,
    )
    assert sent.ok
    domain = load_pipeline_config().model_copy(update={"allowlist": ["elsewhere.test"]})
    other = _note(tmp_path, email="second@elsewhere.test", name="B2B-002-20261120T000000000000Z")
    domain_send = deliver(
        tmp_path,
        other[0],
        "gmail",
        "send",
        True,
        demo_safety=True,
        client=FakeMailbox(account="owner@example.com"),
        config=domain,
    )
    assert domain_send.ok


def test_demo_off_sends_only_after_confirmation(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path, email="stranger@elsewhere.test")
    client = FakeMailbox(account="owner@example.com")
    early = deliver(tmp_path, run, "gmail", "send", False, demo_safety=False, client=client)
    assert early.ok is False
    assert "confirmation" in early.message
    assert client.calls == []
    sent = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert sent.ok
    assert client.calls[0][0] == "send"


def test_own_address_is_allowlisted_in_demo_mode(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path, email="owner@example.com")
    client = FakeMailbox(account="owner@example.com")
    config = load_pipeline_config().model_copy(update={"allowlist": []})
    sent = deliver(
        tmp_path,
        run,
        "gmail",
        "send",
        True,
        demo_safety=True,
        client=client,
        config=config,
    )
    assert sent.ok
    assert sent.message_id == "sent-1"
    assert client.calls[0][1] == "owner@example.com"
    assert client.calls[0][4] == "owner@example.com"


def test_one_confirmed_send_per_run(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path)
    client = FakeMailbox(account="owner@example.com")
    first = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert first.ok
    second = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert second.ok is False
    assert "already sent" in second.message.lower()
    assert [item[0] for item in client.calls] == ["send"]
    drafted = deliver(tmp_path, run, "outlook", "draft", client=client)
    assert drafted.ok
    assert [item[0] for item in client.calls] == ["send", "draft"]
    saved = json.loads((run / "mail.json").read_text(encoding="utf-8"))
    assert saved["confirmed_send"]["message_id"] == "sent-1"
    assert saved["last_draft"]["message_id"] == "draft-1"


def test_send_cap_stops_send_now_and_still_allows_a_draft(tmp_path):
    config = load_pipeline_config().model_copy(update={"send_cap": 2})
    assert load_pipeline_config().send_cap == 5
    client = FakeMailbox()
    for index, name in enumerate(("B2B-001-cap-a", "B2B-001-cap-b")):
        run = _note(tmp_path, name=name)[0]
        result = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client, config=config)
        assert result.ok, index
    blocked_run = _note(tmp_path, name="B2B-001-cap-c")[0]
    blocked = deliver(
        tmp_path,
        blocked_run,
        "gmail",
        "send",
        True,
        demo_safety=False,
        client=client,
        config=config,
    )
    assert blocked.ok is False
    assert "turned off" in blocked.message
    drafted = deliver(tmp_path, blocked_run, "gmail", "draft", client=client, config=config)
    assert drafted.ok


def test_kill_switch_blocks_draft_and_send(monkeypatch, tmp_path):
    run, _profile, _subject, _body = _note(tmp_path)
    client = FakeMailbox()
    monkeypatch.setenv("LEADGEN_KILL_SWITCH", "1")
    drafted = deliver(tmp_path, run, "gmail", "draft", client=client)
    sent = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert "Kill switch" in drafted.message
    assert "Kill switch" in sent.message
    assert client.calls == []


def test_missing_email_is_refused(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path, email="")
    client = FakeMailbox()
    drafted = deliver(tmp_path, run, "gmail", "draft", client=client)
    sent = deliver(tmp_path, run, "outlook", "send", True, demo_safety=False, client=client)
    assert drafted.message == "This record has no email, so it cannot be drafted or sent."
    assert sent.message == drafted.message
    assert client.calls == []


def test_expired_token_asks_for_reconnect_and_does_not_mark_sent(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path)
    secret = secrets.token_hex(24)
    other = secrets.token_hex(24)
    client = FakeMailbox(error=SignInExpired(secret))
    client.token = secret
    client.client_secret = other
    result = deliver(tmp_path, run, "gmail", "send", True, demo_safety=False, client=client)
    assert result.ok is False
    assert result.reconnect is True
    assert result.message == "The sign-in expired. Reconnect, then try again."
    assert secret not in result.message
    assert other not in result.message
    assert not (run / "mail.json").is_file()
    blob = (tmp_path / "runs" / "flight_recorder.jsonl").read_text(encoding="utf-8")
    assert secret not in blob
    assert other not in blob
    assert "UNIQUE-BODY-SENTINEL" not in blob
    _assert_absent_from_repo(secret)
    _assert_absent_from_repo(other)


def test_provider_and_network_errors_leave_the_note_unsent(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path)
    rejected = deliver(
        tmp_path,
        run,
        "gmail",
        "send",
        True,
        demo_safety=False,
        client=FakeMailbox(error=ProviderRejected("secret-body")),
    )
    assert rejected.reconnect is True
    assert rejected.message == "The mail service did not accept this note. Nothing was sent."
    assert "secret-body" not in rejected.message
    offline = deliver(
        tmp_path,
        run,
        "outlook",
        "draft",
        client=FakeMailbox(error=MailUnavailable("down")),
    )
    assert offline.reconnect is True
    assert offline.message == "The mail service could not be reached. Nothing was sent."
    assert not (run / "mail.json").is_file()


def test_a_blank_provider_id_is_not_a_send(tmp_path):
    run, _profile, _subject, _body = _note(tmp_path)
    result = deliver(
        tmp_path,
        run,
        "gmail",
        "send",
        True,
        demo_safety=False,
        client=FakeMailbox(blank_id=True),
    )
    assert result.ok is False
    assert not (run / "mail.json").is_file()


def test_connection_status_labels_and_disconnect(monkeypatch, tmp_path):
    token = tmp_path / "gmail-token.json"
    client_file = tmp_path / "gmail-client.json"
    client_file.write_text('{"installed": {"client_id": "not-a-token"}}', encoding="utf-8")
    monkeypatch.setenv("LEADGEN_GMAIL_TOKEN_FILE", str(token))
    monkeypatch.setenv("LEADGEN_GMAIL_CLIENT_FILE", str(client_file))
    assert connection_status("gmail")["label"] == "Not connected"
    secret = secrets.token_hex(24)
    token.write_text(
        json.dumps({"token": secret, "account_email": "ada@example.com"}),
        encoding="utf-8",
    )
    status = connection_status("gmail")
    assert status["label"] == "Connected (ada@example.com)"
    assert secret not in status["label"]
    token.write_text(
        json.dumps({"token": secret, "account_email": "ada@example.com", "sign_in_expired": True}),
        encoding="utf-8",
    )
    assert connection_status("gmail")["label"] == "Expired"
    gone = disconnect_account("gmail")
    assert gone["label"] == "Not connected"
    assert client_file.is_file()
    assert not token.is_file()
    _assert_absent_from_repo(secret)


def test_verifier_and_scoring_do_not_import_mail_clients():
    folder = repo_root() / "src" / "leadgen"
    for name in ("verifier.py", "scoring.py", "metrics.py", "findings.py", "renderer.py", "outbox.py"):
        imported = _imported(folder / name)
        for banned in ("smtplib", "msal", "googleapiclient", "mail"):
            assert banned not in imported


def test_step_five_offers_three_destinations_and_practice_writes_one_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    _note(tmp_path)
    at = _open()
    options = list(at.radio(key="mail_destination").options)
    assert options == ["Practice", "Gmail", "Outlook"]
    at.button(key="save_draft").click().run(timeout=60)
    _ok(at)
    assert len(list((tmp_path / "outbox").glob("*.txt"))) == 1
    assert "already saved" in _text(at).lower()


def test_settings_shows_connection_status(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = _open()
    text = _text(at)
    assert "Gmail: Not connected" in text
    assert "Outlook: Not connected" in text
    assert at.button(key="connect_gmail").label == "Connect"
    assert at.button(key="disconnect_gmail").label == "Disconnect"
    assert at.button(key="connect_outlook").label == "Connect"
    assert at.button(key="disconnect_outlook").label == "Disconnect"


def test_screen_refuses_a_prospect_with_no_email(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    _note(tmp_path, email="", mailing="1 Main Street")
    at = _open()
    text = _text(at)
    assert "This record has no email, so it cannot be drafted or sent." in text
    assert "Mailing address: 1 Main Street" in text
    assert "No email on record" in text
    assert list(at.radio(key="mail_destination").options) == ["Practice", "Gmail", "Outlook"]


def test_expired_sign_in_on_the_page_shows_reconnect(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    run, _profile, _subject, _body = _note(tmp_path)
    monkeypatch.setattr(
        "leadgen.mail.open_client",
        lambda destination: FakeMailbox(error=SignInExpired("hidden-token")),
    )
    at = _open()
    at.radio(key="mail_destination").set_value("Gmail").run(timeout=60)
    at.button(key="save_draft").click().run(timeout=60)
    _ok(at)
    assert at.button(key="reconnect_mail").label == "Reconnect"
    assert "The sign-in expired. Reconnect, then try again." in _text(at)
    assert "hidden-token" not in _text(at)
    assert not (run / "mail.json").is_file()


def _note(tmp_path, email="owner@example.com", approved=True, name="B2B-001-20261120T000000000000Z", mailing="1 Main Street"):
    profile = load_profile("b2b_services")
    run = tmp_path / "runs" / name
    run.mkdir(parents=True)
    body = "\n".join(
        [
            "Hi Ada,",
            "UNIQUE-BODY-SENTINEL",
            profile.sender.name,
            profile.sender.company,
            profile.sender.postal_address,
            profile.opt_out_line,
        ]
    )
    rendered = f"Subject: A short hello\n\n{body}\n"
    (run / "rendered.txt").write_text(rendered, encoding="utf-8")
    (run / "draft.json").write_text(
        json.dumps({"hook": "Hello", "bridge": "A short note."}),
        encoding="utf-8",
    )
    (run / "prospect.json").write_text(
        json.dumps(
            {
                "email": email,
                "contact_name": "Ada Example",
                "mailing_address": mailing,
                "phone": "555-0100",
            }
        ),
        encoding="utf-8",
    )
    (run / "status.json").write_text(
        json.dumps(
            {
                "prospect_id": "B2B-001",
                "profile_id": profile.profile_id,
                "status": "PENDING_APPROVAL",
                "findings": [],
                "evaluator_below_bar": False,
            }
        ),
        encoding="utf-8",
    )
    if approved:
        (run / "approval.json").write_text(
            json.dumps(
                {
                    "decision": "APPROVED",
                    "name": "Ada",
                    "ack_findings": False,
                    "run_id": run.name,
                }
            ),
            encoding="utf-8",
        )
    outbox = tmp_path / "outbox"
    outbox.mkdir(exist_ok=True)
    (outbox / f"{run.name}.txt").write_text(rendered, encoding="utf-8")
    return run, profile, "A short hello", body + "\n"


def _events(root: Path) -> list[dict]:
    path = root / "runs" / "flight_recorder.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _imported(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _assert_absent_from_repo(secret: str) -> None:
    skip = {".git", ".venv", "__pycache__", ".pytest_cache", "runs", "outbox"}
    for path in repo_root().rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert secret not in text


def _open():
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    _ok(at)
    return at


def _ok(at):
    assert list(at.exception) == []


def _text(at) -> str:
    chunks = []
    for name in (
        "markdown",
        "header",
        "info",
        "error",
        "success",
        "warning",
        "caption",
        "text",
        "code",
    ):
        block = getattr(at, name, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None) or getattr(item, "label", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)
