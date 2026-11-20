"""Real vendor calls. Skipped unless LEADGEN_LIVE_TESTS=1."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LEADGEN_LIVE_TESTS") != "1",
    reason="Set LEADGEN_LIVE_TESTS=1 to call the vendors.",
)


def test_check_keys_live(monkeypatch):
    monkeypatch.delenv("LEADGEN_ENV_FILE", raising=False)
    monkeypatch.setenv("LEADGEN_LLM_MODE", "live")
    from leadgen.check_keys import main

    assert main() == 0


def test_b2b_004_live(monkeypatch, tmp_path):
    monkeypatch.delenv("LEADGEN_ENV_FILE", raising=False)
    monkeypatch.setenv("LEADGEN_LLM_MODE", "live")
    from leadgen.loaders import load_prospects
    from leadgen.pipeline import run_prospect
    from leadgen.profiles import load_pipeline_config, load_profile

    profile = load_profile("b2b_services")
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == "B2B-004")
    result = run_prospect(profile, prospect, load_pipeline_config(), tmp_path)
    assert result.status in {"PENDING_APPROVAL", "BLOCKED"}
    assert result.run_dir is not None
