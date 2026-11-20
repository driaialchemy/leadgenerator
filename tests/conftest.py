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
    ):
        monkeypatch.delenv(name, raising=False)
