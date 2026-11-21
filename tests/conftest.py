"""Keep pytest offline and away from the real key file."""

import pytest


@pytest.fixture(autouse=True)
def offline_env(monkeypatch, tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("LEADGEN_LLM_MODE=offline\n", encoding="utf-8")
    monkeypatch.setenv("LEADGEN_ENV_FILE", str(env_file))
    monkeypatch.setenv("LEADGEN_LLM_MODE", "offline")
    monkeypatch.delenv("LEADGEN_DEMO_TEMPT", raising=False)
    for name in (
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "LEADGEN_TAILOR_PROVIDER",
        "LEADGEN_TAILOR_MODEL",
        "LEADGEN_DRAFTER_PROVIDER",
        "LEADGEN_DRAFTER_MODEL",
        "LEADGEN_EVALUATOR_PROVIDER",
        "LEADGEN_EVALUATOR_MODEL",
        "LEADGEN_TRANSLATOR_PROVIDER",
        "LEADGEN_TRANSLATOR_MODEL",
        "LEADGEN_REASON_PROVIDER",
        "LEADGEN_REASON_MODEL",
        "SAM_API_KEY",
        "LEADGEN_EDGAR_USER_AGENT",
        "LEADGEN_GMAIL_CLIENT_FILE",
        "LEADGEN_GMAIL_TOKEN_FILE",
        "LEADGEN_OUTLOOK_CLIENT_ID",
        "LEADGEN_OUTLOOK_TOKEN_FILE",
        "LEADGEN_OUTLOOK_TENANT",
    ):
        monkeypatch.delenv(name, raising=False)
