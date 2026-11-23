"""Draft or send one approved note from the signed-in mailbox.

Practice never calls a provider. Gmail and Outlook are lazy-imported.
This module does not list or read mailbox messages, and it never logs a token.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from leadgen.flight_recorder import append_event, recorder_path
from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.llm import current_mode, scrub
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import FlightEvent

GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.compose",)
GRAPH_SCOPES = (
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.ReadWrite",
)

NO_EMAIL = "This record has no email, so it cannot be drafted or sent."
NOT_APPROVED = "This note has not been approved, so it cannot be drafted or sent."
EXPIRED = "The sign-in expired. Reconnect, then try again."
UNREACHABLE = "The mail service could not be reached. Nothing was sent."
REJECTED_BY_PROVIDER = "The mail service did not accept this note. Nothing was sent."
NEEDS_CONFIRMATION = "Send now needs a second confirmation."
PLACEHOLDER_SEND = (
    "Add the real sender name, address, and phone in the settings file before sending"
)
ALREADY_SENT = "This note was already sent. A new draft is still allowed."
NOT_CONNECTED = "This account is not connected. Reconnect, then try again."
MISSING_IDENTITY = "The note is missing the sender identity or the opt-out line."
DEMO_BLOCK = (
    "Demo safety is on. This address is not on the allowlist, "
    "so it can only be saved as a draft."
)

_session_sends = 0


class SignInExpired(Exception):
    """The saved sign-in can no longer be used."""


class ProviderRejected(Exception):
    """The provider refused the draft or the send."""


class MailUnavailable(Exception):
    """The provider could not be reached."""


class MailProblem(Exception):
    """A plain message this module wrote. It never carries a token."""

    def __init__(self, message: str, reconnect: bool = False):
        super().__init__(message)
        self.reconnect = reconnect


@dataclass
class MailResult:
    ok: bool
    message: str
    reconnect: bool = False
    message_id: str = ""


def reset_session_sends() -> None:
    """Start the per-session send count over. Tests use this."""
    global _session_sends
    _session_sends = 0


def session_sends() -> int:
    return _session_sends


def connection_status(destination: str) -> dict:
    """Connected, Not connected, or Expired. The label never includes a token."""
    path = _token_path(destination)
    if path is None or not path.is_file():
        return _label("missing", "")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _label("expired", "")
    address = str(data.get("account_email") or data.get("account") or "")
    if data.get("sign_in_expired"):
        return _label("expired", address)
    expiry = data.get("expiry")
    if expiry and not data.get("refresh_token"):
        try:
            moment = datetime.fromisoformat(str(expiry))
        except ValueError:
            moment = None
        if moment is not None:
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            if moment < datetime.now(timezone.utc):
                return _label("expired", address)
    if not address and not data.get("token") and not data.get("cache"):
        return _label("missing", "")
    return _label("connected", address)


def connect_account(destination: str) -> dict:
    """Sign in and save a token under the path named in the key file."""
    try:
        client = open_client(destination)
    except SignInExpired:
        _mark_expired(destination)
        return connection_status(destination)
    except MailProblem:
        return connection_status(destination)
    return _label("connected", getattr(client, "account", ""))


def disconnect_account(destination: str) -> dict:
    """Delete the saved token. The client file stays where it is."""
    path = _token_path(destination)
    if path is not None and path.is_file():
        path.unlink()
    return connection_status(destination)


def open_client(destination: str):
    """Build the provider client. Imported only when a mailbox is used."""
    kind = _destination(destination)
    if kind == "gmail":
        return _GmailClient()
    if kind == "outlook":
        return _OutlookClient()
    raise MailProblem("Choose Gmail or Outlook.")


def refusal_reason(
    root: Path,
    run_dir: Path,
    destination: str,
    action: str,
    *,
    demo_safety: bool = True,
    confirmed: bool = True,
    account: str = "",
    config=None,
) -> str:
    """Why Send now or a draft must stop. Empty means the provider may be called."""
    kind = _destination(destination)
    verb = _action(action)
    if not kind or not verb:
        return "Choose Practice, Gmail, or Outlook."
    try:
        assert_not_engaged(root)
    except KillSwitchEngaged as exc:
        return str(exc)
    approval = _approval(run_dir)
    if approval is None:
        return NOT_APPROVED
    if kind == "practice":
        return ""
    if verb == "send" and kind in {"gmail", "outlook"} and _placeholder_sender(run_dir):
        return PLACEHOLDER_SEND
    if not _recipient(run_dir):
        return NO_EMAIL
    rendered = _rendered(run_dir)
    if not _identity_ok(run_dir, rendered):
        return MISSING_IDENTITY
    if verb == "send" and _already_sent(run_dir):
        return ALREADY_SENT
    if verb == "send" and not confirmed:
        return NEEDS_CONFIRMATION
    cap, allowlist = _mail_config(config)
    if verb == "send" and demo_safety and not _listed(_recipient(run_dir), account, allowlist):
        return DEMO_BLOCK
    if verb == "send" and _session_sends >= cap:
        return f"The send limit for this session is {cap}. Send now is turned off."
    return ""


def deliver(
    root: Path,
    run_dir: Path,
    destination: str,
    action: str,
    confirmed: bool = False,
    *,
    demo_safety: bool = True,
    client=None,
    config=None,
) -> MailResult:
    """Draft or send one approved note. Refusals happen before any provider call."""
    folder = Path(root)
    run = Path(run_dir)
    kind = _destination(destination)
    verb = _action(action)
    approval = _approval(run)
    approver = approval["name"].strip() if approval else ""
    approved_at = _approved_at(run) if approval else ""
    recipient = _recipient(run)
    try:
        assert_not_engaged(folder)
    except KillSwitchEngaged as exc:
        _log(folder, run.name, "kill_switch_block", "blocked", str(exc), approver=approver)
        return MailResult(False, str(exc))
    reason = refusal_reason(
        folder,
        run,
        kind,
        verb,
        demo_safety=demo_safety,
        confirmed=confirmed,
        account=getattr(client, "account", "") if client is not None else "",
        config=config,
    )
    if reason == NOT_APPROVED or approval is None and reason:
        _log(
            folder,
            run.name,
            "mail_send" if verb == "send" else "mail_draft",
            "blocked",
            "refused",
            destination=kind,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, reason or NOT_APPROVED)
    if reason and kind == "practice":
        return MailResult(False, reason)
    if kind == "practice":
        ready = (folder / "outbox" / f"{run.name}.txt").is_file()
        if verb == "send":
            text = "Practice saves a file. It does not email."
        elif ready:
            text = "This note is already saved as a practice file."
        else:
            text = "The practice file is not in the outbox."
        _log(
            folder,
            run.name,
            "mail_draft",
            "ok" if ready and verb == "draft" else "blocked",
            "saved" if ready and verb == "draft" else "refused",
            destination="practice",
            recipient=recipient,
            approver=approver,
        )
        return MailResult(ready and verb == "draft", text)
    if reason and client is None and "allowlist" in reason:
        status = connection_status(kind)
        reason = refusal_reason(
            folder,
            run,
            kind,
            verb,
            demo_safety=demo_safety,
            confirmed=confirmed,
            account=status.get("address", ""),
            config=config,
        )
    if reason:
        _log(
            folder,
            run.name,
            "mail_send" if verb == "send" else "mail_draft",
            "blocked",
            "refused",
            destination=kind,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, reason)
    try:
        mailbox = client if client is not None else open_client(kind)
    except SignInExpired:
        _mark_expired(kind)
        _log(folder, run.name, _event(verb), "fail", "expired", destination=kind, recipient=recipient, approver=approver)
        return MailResult(False, EXPIRED, True)
    except MailProblem as exc:
        return MailResult(False, str(exc), exc.reconnect)
    account = str(getattr(mailbox, "account", "") or "")
    reason = refusal_reason(
        folder,
        run,
        kind,
        verb,
        demo_safety=demo_safety,
        confirmed=confirmed,
        account=account,
        config=config,
    )
    if reason:
        _log(
            folder,
            run.name,
            _event(verb),
            "blocked",
            "refused",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        reconnect = reason == NOT_CONNECTED or reason == EXPIRED
        return MailResult(False, reason, reconnect)
    subject, body = _split(_rendered(run))
    try:
        if verb == "send":
            message_id = mailbox.send(recipient, subject, body, account)
        else:
            message_id = mailbox.draft(recipient, subject, body, account)
    except SignInExpired:
        _mark_expired(kind)
        _log(
            folder,
            run.name,
            _event(verb),
            "fail",
            "expired",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, EXPIRED, True)
    except MailUnavailable:
        _log(
            folder,
            run.name,
            _event(verb),
            "fail",
            "unreachable",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, UNREACHABLE, True)
    except ProviderRejected:
        _log(
            folder,
            run.name,
            _event(verb),
            "fail",
            "rejected",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, REJECTED_BY_PROVIDER, True)
    except Exception:
        _log(
            folder,
            run.name,
            _event(verb),
            "fail",
            "rejected",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, REJECTED_BY_PROVIDER, True)
    message_id = str(message_id or "").strip()
    if not message_id:
        _log(
            folder,
            run.name,
            _event(verb),
            "fail",
            "rejected",
            destination=kind,
            account=account,
            recipient=recipient,
            approver=approver,
        )
        return MailResult(False, REJECTED_BY_PROVIDER, True)
    _store(
        run,
        verb,
        kind,
        account,
        recipient,
        message_id,
        approver,
        approved_at,
    )
    _log(
        folder,
        run.name,
        _event(verb),
        "ok",
        "sent" if verb == "send" else "drafted",
        destination=kind,
        account=account,
        recipient=recipient,
        message_id=message_id,
        approver=approver,
    )
    if verb == "send":
        global _session_sends
        _session_sends += 1
        return MailResult(True, "Sent.", False, message_id)
    return MailResult(True, "Saved as a draft.", False, message_id)


def _event(verb: str) -> str:
    return "mail_send" if verb == "send" else "mail_draft"


def _destination(destination: str) -> str:
    text = (destination or "").strip().lower()
    if text in {"practice", "gmail", "outlook"}:
        return text
    return ""


def _action(action: str) -> str:
    text = (action or "").strip().lower()
    if text in {"draft", "save as draft"}:
        return "draft"
    if text in {"send", "send now"}:
        return "send"
    return ""


def _mail_config(config) -> tuple[int, list[str]]:
    loaded = config if config is not None else load_pipeline_config()
    return int(loaded.send_cap), list(loaded.allowlist)


def _listed(recipient: str, account: str, allowlist: list[str]) -> bool:
    target = recipient.strip().lower()
    owner = account.strip().lower()
    if owner and target == owner:
        return True
    for raw in allowlist:
        entry = raw.strip().lower()
        if not entry:
            continue
        if entry.startswith("@") and target.endswith(entry):
            return True
        if "@" in entry and target == entry:
            return True
        if "@" not in entry and target.endswith("@" + entry):
            return True
    return False


def _approval(run_dir: Path) -> dict | None:
    path = Path(run_dir) / "approval.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if data.get("decision") not in {"APPROVED", "EDITED"}:
        return None
    if not str(data.get("name") or "").strip():
        return None
    return data


def _approved_at(run_dir: Path) -> str:
    path = Path(run_dir) / "approval.json"
    moment = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return moment.isoformat()


def _recipient(run_dir: Path) -> str:
    path = Path(run_dir) / "prospect.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    return str(data.get("email") or "").strip()


def _rendered(run_dir: Path) -> str:
    path = Path(run_dir) / "rendered.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _identity_ok(run_dir: Path, rendered: str) -> bool:
    status_path = Path(run_dir) / "status.json"
    if not status_path.is_file() or not rendered.strip():
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        profile = load_profile(str(status.get("profile_id") or ""))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    sender = profile.sender
    required = [sender.name, sender.company, sender.postal_address, profile.opt_out_line]
    if sender.phone.strip():
        required.append(sender.phone)
    return all(part and part in rendered for part in required)


def _placeholder_sender(run_dir: Path) -> bool:
    status_path = Path(run_dir) / "status.json"
    if not status_path.is_file():
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        profile = load_profile(str(status.get("profile_id") or ""))
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    marked = set(profile.sender.placeholder_fields)
    return bool(marked & {"name", "postal_address", "phone"})


def _split(rendered: str) -> tuple[str, str]:
    text = rendered.replace("\r\n", "\n")
    if text.startswith("Subject:"):
        first, _, rest = text.partition("\n")
        return first.split(":", 1)[1].strip(), rest.lstrip("\n")
    return "", text


def _already_sent(run_dir: Path) -> bool:
    path = Path(run_dir) / "mail.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    sent = data.get("confirmed_send")
    return isinstance(sent, dict) and bool(str(sent.get("message_id") or "").strip())


def _store(run_dir, verb, destination, account, recipient, message_id, approver, approved_at) -> None:
    path = Path(run_dir) / "mail.json"
    current = {}
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = {}
    record = {
        "destination": destination,
        "account": account,
        "recipient": recipient,
        "message_id": message_id,
        "result": "sent" if verb == "send" else "drafted",
    }
    current["approver"] = approver
    current["approved_at"] = approved_at
    if verb == "send":
        current["confirmed_send"] = record
    else:
        current["last_draft"] = record
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")


def _log(
    root: Path,
    run_id: str,
    event_type: str,
    status: str,
    detail: str,
    **fields,
) -> None:
    mode = "offline"
    try:
        mode = current_mode()
    except Exception:
        mode = "offline"
    clean = {}
    for key, value in fields.items():
        if value is None:
            continue
        clean[key] = scrub(value) if isinstance(value, str) else value
    event = FlightEvent(
        event_id=str(uuid4()),
        ts=datetime.now(timezone.utc).isoformat(),
        run_id=run_id,
        event_type=event_type,
        actor="mail",
        mode=mode if mode in {"offline", "live"} else "offline",
        status=status,
        detail=scrub(detail),
        **clean,
    )
    append_event(event, recorder_path(root))


def _label(state: str, address: str) -> dict:
    if state == "connected":
        label = f"Connected ({address})" if address else "Connected"
    elif state == "expired":
        label = "Expired"
    else:
        state = "missing"
        label = "Not connected"
    return {"state": state, "address": address, "label": label}


def _token_path(destination: str) -> Path | None:
    kind = _destination(destination)
    name = {
        "gmail": "LEADGEN_GMAIL_TOKEN_FILE",
        "outlook": "LEADGEN_OUTLOOK_TOKEN_FILE",
    }.get(kind, "")
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw)


def _mark_expired(destination: str) -> None:
    path = _token_path(destination)
    if path is None or not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    data["sign_in_expired"] = True
    path.write_text(json.dumps(data), encoding="utf-8")


class _GmailClient:
    """Gmail compose scope only. Drafts and sends. Does not list or read mail."""

    def __init__(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError:
            raise MailProblem("Gmail support is not installed.") from None
        client_file = os.environ.get("LEADGEN_GMAIL_CLIENT_FILE", "").strip()
        token_path = _token_path("gmail")
        if not client_file or token_path is None:
            raise MailProblem(NOT_CONNECTED, True)
        creds = None
        stored_address = ""
        if token_path.is_file():
            payload = json.loads(token_path.read_text(encoding="utf-8"))
            stored_address = str(payload.pop("account_email", "") or "")
            expired_flag = bool(payload.pop("sign_in_expired", False))
            if not expired_flag:
                creds = Credentials.from_authorized_user_info(payload, list(GMAIL_SCOPES))
        if creds is not None and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if creds is None or not creds.valid:
            if not Path(client_file).is_file():
                raise MailProblem(NOT_CONNECTED, True)
            flow = InstalledAppFlow.from_client_secrets_file(client_file, list(GMAIL_SCOPES))
            creds = flow.run_local_server(port=0)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        try:
            profile = service.users().getProfile(userId="me").execute()
            address = str(profile.get("emailAddress") or stored_address)
        except Exception:
            address = stored_address
        if not address:
            raise SignInExpired()
        self.account = address
        self._service = service
        _write_gmail_token(creds, address, token_path)

    def draft(self, recipient: str, subject: str, body: str, account: str) -> str:
        created = _gmail_execute(
            lambda: self._service.users().drafts().create(
                userId="me",
                body={"message": {"raw": _raw_message(recipient, subject, body, account)}},
            ).execute()
        )
        message = created.get("message") or {}
        return str(created.get("id") or message.get("id") or "")

    def send(self, recipient: str, subject: str, body: str, account: str) -> str:
        sent = _gmail_execute(
            lambda: self._service.users().messages().send(
                userId="me",
                body={"raw": _raw_message(recipient, subject, body, account)},
            ).execute()
        )
        return str(sent.get("id") or "")


class _OutlookClient:
    """Graph Mail.Send and Mail.ReadWrite. Creates a draft, and sends that draft.

    Mail.ReadWrite can read mail. This client never lists or reads messages.
    """

    def __init__(self):
        try:
            import msal
        except ImportError:
            raise MailProblem("Outlook support is not installed.") from None
        client_id = os.environ.get("LEADGEN_OUTLOOK_CLIENT_ID", "").strip()
        token_path = _token_path("outlook")
        if not client_id or token_path is None:
            raise MailProblem(NOT_CONNECTED, True)
        tenant = os.environ.get("LEADGEN_OUTLOOK_TENANT", "").strip() or "consumers"
        cache = msal.SerializableTokenCache()
        stored = {}
        if token_path.is_file():
            stored = json.loads(token_path.read_text(encoding="utf-8"))
            if stored.get("cache"):
                cache.deserialize(stored["cache"])
        app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant}",
            token_cache=cache,
        )
        result = None
        accounts = app.get_accounts()
        if accounts and not stored.get("sign_in_expired"):
            result = app.acquire_token_silent(list(GRAPH_SCOPES), account=accounts[0])
        if not result or "access_token" not in result:
            result = app.acquire_token_interactive(scopes=list(GRAPH_SCOPES))
        if not result or "access_token" not in result:
            raise SignInExpired()
        claims = result.get("id_token_claims") or {}
        account = str(claims.get("preferred_username") or claims.get("email") or "")
        if not account and isinstance(result.get("account"), dict):
            account = str(result["account"].get("username") or "")
        if not account:
            account = str(stored.get("account") or "")
        if not account:
            raise SignInExpired()
        self.account = account
        self._token = result["access_token"]
        _write_outlook_token(cache, account, token_path)

    def draft(self, recipient: str, subject: str, body: str, account: str) -> str:
        del account
        _status, payload = _graph(
            "POST",
            "https://graph.microsoft.com/v1.0/me/messages",
            self._token,
            _graph_message(recipient, subject, body),
        )
        return str(payload.get("id") or "")

    def send(self, recipient: str, subject: str, body: str, account: str) -> str:
        message_id = self.draft(recipient, subject, body, account)
        if not message_id:
            raise ProviderRejected()
        status, _payload = _graph(
            "POST",
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/send",
            self._token,
            None,
        )
        if status not in {200, 202}:
            raise ProviderRejected()
        return message_id


def _gmail_execute(call):
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        raise MailProblem("Gmail support is not installed.") from None
    try:
        return call()
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in {401, 403}:
            raise SignInExpired() from None
        raise ProviderRejected() from None


def _raw_message(recipient: str, subject: str, body: str, account: str) -> str:
    import base64
    from email.message import EmailMessage

    message = EmailMessage()
    message["To"] = recipient
    message["From"] = account
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _graph_message(recipient: str, subject: str, body: str) -> dict:
    return {
        "subject": subject,
        "body": {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": recipient}}],
    }


def _graph(method: str, url: str, token: str, payload: dict | None):
    import urllib.error
    import urllib.request

    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SignInExpired() from None
        raise ProviderRejected() from None
    except urllib.error.URLError:
        raise MailUnavailable() from None
    if not raw:
        return status, {}
    return status, json.loads(raw.decode("utf-8"))


def _write_gmail_token(creds, address: str, path: Path) -> None:
    payload = json.loads(creds.to_json())
    payload["account_email"] = address
    payload["sign_in_expired"] = False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_outlook_token(cache, address: str, path: Path) -> None:
    payload = {
        "cache": cache.serialize(),
        "account": address,
        "sign_in_expired": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
