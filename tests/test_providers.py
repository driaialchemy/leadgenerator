"""Three vendors, a private env file, and no keys in the log."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from leadgen.check_keys import main as check_keys
from leadgen.llm import (
    ConfigError,
    call_model,
    candidate_env_files,
    load_project_env,
)
from leadgen.loaders import load_prospects
from leadgen.messages import drafter_prompt
from leadgen.paths import repo_root
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import TailorResult

ROOT = repo_root()
FAKE_KEY = "unit-test-key-value-9f3a"


def test_each_role_uses_its_provider(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr("google.genai.Client", _google_client(seen))
    monkeypatch.setattr("leadgen.llm.anthropic.Anthropic", _anthropic_client(seen))
    monkeypatch.setattr("openai.OpenAI", _openai_client(seen))
    for role, key_name in (
        ("tailor", "GOOGLE_API_KEY"),
        ("drafter", "ANTHROPIC_API_KEY"),
        ("evaluator", "OPENAI_API_KEY"),
    ):
        monkeypatch.setenv(key_name, "present")
        call_model(role, "Hello", tmp_path)
    assert [item[0] for item in seen] == ["google", "anthropic", "openai"]
    assert [item[1] for item in seen] == [
        "gemini-4-argon",
        "claude-fable-5-2",
        "gpt-6.2-astra",
    ]


def test_provider_override_is_honored(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr("openai.OpenAI", _openai_client(seen))
    monkeypatch.setenv("OPENAI_API_KEY", "present")
    monkeypatch.setenv("LEADGEN_TAILOR_PROVIDER", "openai")
    monkeypatch.setenv("LEADGEN_TAILOR_MODEL", "custom-model")
    call_model("tailor", "Hello", tmp_path)
    assert seen == [("openai", "custom-model")]


def test_missing_key_names_the_variable_and_skips_the_sdk(monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise AssertionError("SDK client was constructed")

    monkeypatch.setattr("google.genai.Client", explode)
    monkeypatch.setattr("leadgen.llm.anthropic.Anthropic", explode)
    monkeypatch.setattr("openai.OpenAI", explode)
    with pytest.raises(ConfigError) as caught:
        call_model("tailor", "Hello", tmp_path)
    assert "GOOGLE_API_KEY" in str(caught.value)
    assert FAKE_KEY not in str(caught.value)


def test_env_file_lookup_uses_the_first_file_that_exists(monkeypatch, tmp_path):
    first = tmp_path / "first.env"
    second = tmp_path / "second.env"
    first.write_text("LEADGEN_ENV_MARKER=first\n", encoding="utf-8")
    second.write_text(
        "LEADGEN_ENV_MARKER=second\nLEADGEN_ENV_OTHER=second\n", encoding="utf-8"
    )
    monkeypatch.delenv("LEADGEN_ENV_MARKER", raising=False)
    monkeypatch.delenv("LEADGEN_ENV_OTHER", raising=False)
    assert load_project_env([first, second]) == first
    assert os.environ["LEADGEN_ENV_MARKER"] == "first"
    assert "LEADGEN_ENV_OTHER" not in os.environ
    monkeypatch.delenv("LEADGEN_ENV_MARKER", raising=False)
    assert load_project_env([tmp_path / "missing.env", second]) == second
    assert os.environ["LEADGEN_ENV_MARKER"] == "second"
    monkeypatch.setenv("LEADGEN_ENV_FILE", r"D:\custom\lead.env")
    paths = candidate_env_files()
    assert paths[0] == Path(r"D:\custom\lead.env")
    assert paths[1] == Path(r"C:\Users\msell\secrets\workuity.env")
    assert paths[2] == Path(r"C:\Users\msell\secrets\leadgenerator.env")


def test_red_team_switch_is_drafter_attempt_one_only(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DEMO_TEMPT", "1")
    profile = load_profile("b2b_services")
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == "B2B-001")
    tailor = TailorResult.model_validate_json(
        (ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-001" / "tailor.json").read_text(
            encoding="utf-8"
        )
    )
    first = drafter_prompt(prospect, profile, tailor, attempt=1)
    second = drafter_prompt(prospect, profile, tailor, attempt=2)
    assert "mention an introductory discount" in first
    assert "mention an introductory discount" not in second
    result = run_prospect(profile, prospect, load_pipeline_config(), tmp_path)
    calls = [
        item
        for item in _events(tmp_path)
        if item["event_type"] == "model_call"
        and item["run_id"] == result.run_dir.name
        and item["actor"] == "drafter"
    ]
    assert [item["red_team"] for item in calls] == [True, False]
    assert [item["attempt_number"] for item in calls] == [1, 2]


def test_fake_key_never_appears(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GOOGLE_API_KEY", FAKE_KEY)

    def boom(**kwargs):
        raise RuntimeError(f"upstream failed {kwargs.get('api_key')}")

    monkeypatch.setattr("google.genai.Client", boom)
    with pytest.raises(ConfigError) as caught:
        call_model("tailor", "Hello", tmp_path)
    assert FAKE_KEY not in str(caught.value)
    assert FAKE_KEY not in capsys.readouterr().out

    profile = load_profile("b2b_services")
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == "B2B-004")
    run_prospect(profile, prospect, load_pipeline_config(), tmp_path)
    blob = _tree_text(tmp_path / "runs")
    assert FAKE_KEY not in blob
    out = check_keys()
    printed = capsys.readouterr().out
    assert FAKE_KEY not in printed
    assert "key no" in printed or "call fail" in printed
    assert out == 1


def test_tracked_files_have_no_key_shapes():
    import re

    patterns = (
        re.compile(r"(?<![A-Za-z])" + "s" + "k-"),
        re.compile("AI" + "za"),
        re.compile("s" + "k-" + "ant-"),
    )
    skip = {".venv", ".git", "__pycache__", ".pytest_cache", "runs", "outbox"}
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            name for name in dirnames if name not in skip and "egg-info" not in name
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if name == ".env" or path.suffix == ".env":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(pattern.search(text) for pattern in patterns):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def _events(root):
    path = root / "runs" / "flight_recorder.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _tree_text(folder: Path) -> str:
    parts = []
    for path in folder.rglob("*"):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _google_client(seen):
    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def generate_content(self, model, contents):
            seen.append(("google", model))
            usage = SimpleNamespace(prompt_token_count=3, candidates_token_count=2)
            return SimpleNamespace(text="{}", usage_metadata=usage)

    return Client


def _anthropic_client(seen):
    class Client:
        def __init__(self, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            seen.append(("anthropic", kwargs["model"]))
            block = SimpleNamespace(text="{}")
            usage = SimpleNamespace(input_tokens=3, output_tokens=2)
            return SimpleNamespace(content=[block], usage=usage)

    return Client


def _openai_client(seen):
    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            seen.append(("openai", kwargs["model"]))
            message = SimpleNamespace(content="{}")
            usage = SimpleNamespace(prompt_tokens=3, completion_tokens=2)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)

    return Client
