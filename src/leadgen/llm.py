"""Model calls. Live is the class default. Offline replay is the backup."""

import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from leadgen.kill_switch import assert_not_engaged
from leadgen.paths import repo_root


class ConfigError(RuntimeError):
    """A key or a setting is missing. This is not a vendor failure."""


class ProviderError(RuntimeError):
    """A vendor refused or dropped the call. The message is one scrubbed line."""

    def __init__(
        self,
        role: str,
        provider: str,
        model: str,
        status: int | str,
        reason: str,
    ):
        self.role = role
        self.provider = provider
        self.model = model
        self.status = status
        self.reason = reason
        super().__init__(self.line())

    def line(self) -> str:
        prefix = str(self.status)
        if self.reason == prefix or self.reason.startswith(prefix + " "):
            return self.reason
        return f"{prefix} {self.reason}".strip()


class ModelResponse:
    """Text from one role, plus the facts the logbook is allowed to keep."""

    def __init__(
        self,
        text: str,
        provider: str,
        model: str,
        duration_ms: int | None,
        input_tokens: int | None,
        output_tokens: int | None,
        red_team: bool,
    ):
        self.text = text
        self.provider = provider
        self.model = model
        self.duration_ms = duration_ms
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.red_team = red_team


_DEFAULTS = {
    "tailor": ("google", "gemini-4-argon"),
    "drafter": ("anthropic", "claude-fable-5-2"),
    "evaluator": ("openai", "gpt-6.2-astra"),
    "translator": ("google", "gemini-4-argon"),
    "reason": ("google", "gemini-4-argon"),
}
_KEYS = {
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}
_TIMEOUT_SECONDS = 60


def candidate_env_files() -> list[Path]:
    """First existing file wins. A missing override is skipped."""
    paths: list[Path] = []
    named = os.environ.get("LEADGEN_ENV_FILE", "").strip()
    if named:
        paths.append(Path(named))
    paths.append(Path(r"C:\Users\msell\secrets\workuity.env"))
    paths.append(Path(r"C:\Users\msell\secrets\leadgenerator.env"))
    return paths


def load_project_env(
    candidates: list[Path] | None = None, override: bool = False
) -> Path | None:
    """Fill unset settings from Streamlit secrets, then the first env file that exists.

    A variable already in the environment is never replaced. Returns the env file path, or None.
    """
    from leadgen.cloud import load_streamlit_secrets

    load_streamlit_secrets()
    for path in candidates if candidates is not None else candidate_env_files():
        if path.is_file():
            load_dotenv(path, override=override)
            return path
    return None


def current_mode() -> str:
    """live unless LEADGEN_LLM_MODE is offline. A set variable is left alone."""
    load_project_env()
    mode = os.environ.get("LEADGEN_LLM_MODE", "live").strip() or "live"
    if mode not in {"offline", "live"}:
        raise ConfigError(f"LEADGEN_LLM_MODE must be offline or live, not {mode!r}.")
    return mode


def role_config(role: str) -> tuple[str, str, str]:
    """Provider, model, and the env var that holds the key."""
    if role not in _DEFAULTS:
        raise ConfigError(f"Unknown role {role!r}.")
    provider, model = _DEFAULTS[role]
    provider = os.environ.get(f"LEADGEN_{role.upper()}_PROVIDER", "").strip() or provider
    model = os.environ.get(f"LEADGEN_{role.upper()}_MODEL", "").strip() or model
    if provider not in _KEYS:
        raise ConfigError(f"Unknown provider {provider!r}.")
    return provider, model, _KEYS[provider]


def scrub(text: str) -> str:
    """Remove key values from a string before it is printed or stored."""
    cleaned = text
    names = list(_KEYS.values()) + ["SAM_API_KEY", "LEADGEN_EDGAR_USER_AGENT", "CENSUS_API_KEY"]
    for name in names:
        value = os.environ.get(name, "").strip()
        if len(value) >= 8:
            cleaned = cleaned.replace(value, "")
    return " ".join(cleaned.split())


def call_model(
    role: str, prompt: str, root: Path | None = None, red_team: bool = False
) -> ModelResponse:
    """One live vendor call. The kill switch is checked first."""
    folder = Path(root) if root is not None else repo_root()
    assert_not_engaged(folder)
    load_project_env()
    provider, model, key_name = role_config(role)
    key = os.environ.get(key_name, "").strip()
    if not key:
        raise ConfigError(f"{key_name} is required for the {role}.")
    started = time.perf_counter()
    text, input_tokens, output_tokens = _invoke(role, provider, model, key, prompt)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return ModelResponse(
        text, provider, model, duration_ms, input_tokens, output_tokens, red_team
    )


def complete(
    role: str,
    prompt: str,
    profile_id: str,
    prospect_id: str,
    attempt: int,
    root: Path | None = None,
) -> ModelResponse:
    """Replay a saved answer, or call the role's vendor. The kill switch is first."""
    folder = Path(root) if root is not None else repo_root()
    assert_not_engaged(folder)
    red_team = (
        role == "drafter"
        and attempt == 1
        and os.environ.get("LEADGEN_DEMO_TEMPT", "").strip() == "1"
    )
    if current_mode() != "live":
        provider, model, _key_name = role_config(role)
        text = _offline(role, profile_id, prospect_id, attempt, folder)
        return ModelResponse(text, provider, model, None, None, None, red_team)
    return call_model(role, prompt, folder, red_team)


def _invoke(role: str, provider: str, model: str, key: str, prompt: str):
    try:
        if provider == "google":
            return _google(prompt, model, key)
        if provider == "anthropic":
            return _anthropic(prompt, model, key)
        if provider == "openai":
            return _openai(prompt, model, key)
        raise ConfigError(f"Unknown provider {provider!r}.")
    except (ConfigError, ProviderError):
        raise
    except Exception as exc:
        failure = _provider_error(exc, role, provider, model)
        if failure is not None:
            raise failure from None
        raise ConfigError(scrub(one_line(str(exc)))) from None


def one_line(text: str) -> str:
    """Collapse a vendor message onto one line."""
    flat = " ".join(text.split())
    if len(flat) > 240:
        return flat[:237].rstrip() + "..."
    return flat


def _provider_error(
    exc: Exception, role: str, provider: str, model: str
) -> ProviderError | None:
    """Quota, auth, a missing model, and timeouts. Other bugs stay ConfigError."""
    message = getattr(exc, "message", None) or str(exc)
    reason = scrub(one_line(str(message)))
    name = type(exc).__name__.lower()
    timed_out = "timeout" in name or "timed out" in reason.lower()
    status = _http_status(exc)
    if isinstance(status, int) and status >= 400:
        return ProviderError(role, provider, model, status, reason)
    if timed_out:
        return ProviderError(role, provider, model, "timeout", reason)
    return None


def _http_status(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    return None


def _google(prompt: str, model: str, key: str):
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=key, http_options=types.HttpOptions(timeout=_TIMEOUT_SECONDS * 1000)
    )
    response = client.models.generate_content(model=model, contents=prompt)
    usage = getattr(response, "usage_metadata", None)
    return (
        response.text or "",
        _count(usage, "prompt_token_count"),
        _count(usage, "candidates_token_count"),
    )


def _anthropic(prompt: str, model: str, key: str):
    client = anthropic.Anthropic(api_key=key, timeout=_TIMEOUT_SECONDS)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [block.text for block in message.content if getattr(block, "text", None)]
    usage = getattr(message, "usage", None)
    return "\n".join(parts), _count(usage, "input_tokens"), _count(usage, "output_tokens")


def _openai(prompt: str, model: str, key: str):
    from openai import OpenAI

    client = OpenAI(api_key=key, timeout=_TIMEOUT_SECONDS)
    message = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = getattr(message, "usage", None)
    text = message.choices[0].message.content or ""
    return text, _count(usage, "prompt_tokens"), _count(usage, "completion_tokens")


def _count(usage, name: str) -> int | None:
    if usage is None:
        return None
    value = getattr(usage, name, None)
    if value is None:
        return None
    return int(value)


def _offline(role: str, profile_id: str, prospect_id: str, attempt: int, root: Path) -> str:
    replay = _replay_dir(profile_id, prospect_id, root)
    name = f"{role}.attempt{attempt}.json" if attempt > 1 else f"{role}.json"
    path = replay / name
    if not path.is_file():
        raise FileNotFoundError(f"No replay for {prospect_id} {role} attempt {attempt}.")
    return path.read_text(encoding="utf-8")


def _replay_dir(profile_id: str, prospect_id: str, root: Path) -> Path:
    candidate = root / "sample_data" / "replays" / profile_id / prospect_id
    if candidate.is_dir():
        return candidate
    return repo_root() / "sample_data" / "replays" / profile_id / prospect_id
