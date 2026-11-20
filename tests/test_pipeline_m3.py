"""Offline pipeline: one retry, refusals, and altered replays."""

import json
import shutil
from pathlib import Path

from leadgen.loaders import load_prospects
from leadgen.paths import repo_root
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile

ROOT = repo_root()


def test_b2b_001_retries_the_draft_once(tmp_path):
    result = _run("b2b_services", "B2B-001", tmp_path)
    assert result.status == "PENDING_APPROVAL"
    attempt1 = json.loads((result.run_dir / "verification.attempt1.json").read_text(encoding="utf-8"))
    codes = {item["code"] for item in attempt1["report"]["blocking"]}
    assert codes == {"raw_fact", "digits", "banned_phrase"}
    attempt2 = json.loads((result.run_dir / "verification.attempt2.json").read_text(encoding="utf-8"))
    assert attempt2["report"]["passed"] is True
    calls = _calls(tmp_path, result.run_dir.name)
    assert sum(1 for item in calls if item["actor"] == "drafter") == 2
    assert sum(1 for item in calls if item["actor"] == "evaluator") == 1


def test_b2b_002_evaluator_sends_the_draft_back(tmp_path):
    result = _run("b2b_services", "B2B-002", tmp_path)
    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert result.status == "PENDING_APPROVAL"
    assert status["evaluator_below_bar"] is False
    retries = [
        item
        for item in _events(tmp_path)
        if item["event_type"] == "retry" and item["run_id"] == result.run_dir.name
    ]
    assert retries
    assert "specificity" in retries[0]["retry_reason"]
    for item in retries:
        assert item["attempt_number"] is not None
        assert item["retry_of"]
        assert item["retry_reason"]


def test_home_002_retries_a_blocked_draft(tmp_path):
    result = _run("home_services", "HOME-002", tmp_path)
    attempt1 = json.loads((result.run_dir / "verification.attempt1.json").read_text(encoding="utf-8"))
    codes = {item["code"] for item in attempt1["report"]["blocking"]}
    assert codes == {"digits", "banned_phrase"}
    attempt2 = json.loads((result.run_dir / "verification.attempt2.json").read_text(encoding="utf-8"))
    assert attempt2["report"]["passed"] is True
    assert result.status == "PENDING_APPROVAL"


def test_clean_prospects_pass_on_the_first_attempt(tmp_path):
    expected = {
        ("b2b_services", "B2B-004"): ["headcount_change"],
        ("home_services", "HOME-001"): [],
        ("home_services", "HOME-004"): ["pricing_question", "system_age_conflict"],
    }
    for (profile_id, prospect_id), findings in expected.items():
        result = _run(profile_id, prospect_id, tmp_path)
        assert result.status == "PENDING_APPROVAL"
        status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
        assert [item["check_id"] for item in status["findings"]] == findings
        calls = _calls(tmp_path, result.run_dir.name)
        assert sum(1 for item in calls if item["actor"] == "drafter") == 1
        assert not any(
            item["event_type"] == "retry" and item["run_id"] == result.run_dir.name
            for item in _events(tmp_path)
        )


def test_ineligible_prospects_are_refused(tmp_path):
    for profile_id, prospect_id in (
        ("b2b_services", "B2B-003"),
        ("b2b_services", "B2B-005"),
    ):
        before = _events(tmp_path)
        result = _run(profile_id, prospect_id, tmp_path)
        assert result.status == "REFUSED"
        assert result.run_dir is None
        added = _events(tmp_path)[len(before):]
        assert added[0]["event_type"] == "refusal"
        assert not any(item["event_type"] == "model_call" for item in added)
    runs = tmp_path / "runs"
    names = [path.name for path in runs.iterdir()] if runs.exists() else []
    assert not any(name.startswith("B2B-003-") or name.startswith("B2B-005-") for name in names)


def test_second_draft_with_a_digit_is_blocked(tmp_path):
    _copy_replay(tmp_path, "b2b_services", "B2B-001")
    caught = {
        "prospect_id": "B2B-001",
        "subject_id": "SUB-B2B-02",
        "claim_ids": ["VP-B2B-02", "VP-B2B-04"],
        "hook": "You mentioned backups and a scare at a sister practice.",
        "bridge": "We can start with step 2 for {{organization}}:",
    }
    _write_replay(tmp_path, "b2b_services", "B2B-001", "drafter.attempt2.json", caught)
    result = _run("b2b_services", "B2B-001", tmp_path)
    assert result.status == "BLOCKED"
    calls = _calls(tmp_path, result.run_dir.name)
    assert sum(1 for item in calls if item["actor"] == "drafter") == 2
    assert sum(1 for item in calls if item["actor"] == "evaluator") == 0


def test_low_evaluator_twice_is_flagged_for_a_person(tmp_path):
    _copy_replay(tmp_path, "b2b_services", "B2B-004")
    low = {
        "relevance": 5,
        "specificity": 2,
        "clarity": 5,
        "tone": 5,
        "suggestions": ["Be more specific."],
    }
    good = json.loads(
        (ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-004" / "drafter.json").read_text(
            encoding="utf-8"
        )
    )
    _write_replay(tmp_path, "b2b_services", "B2B-004", "evaluator.json", low)
    _write_replay(tmp_path, "b2b_services", "B2B-004", "evaluator.attempt2.json", low)
    _write_replay(tmp_path, "b2b_services", "B2B-004", "drafter.attempt2.json", good)
    result = _run("b2b_services", "B2B-004", tmp_path)
    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    assert result.status == "PENDING_APPROVAL"
    assert status["evaluator_below_bar"] is True
    calls = _calls(tmp_path, result.run_dir.name)
    assert sum(1 for item in calls if item["actor"] == "evaluator") == 2


def test_fake_evidence_reruns_the_tailor(tmp_path):
    _copy_replay(tmp_path, "home_services", "HOME-001")
    bad = json.loads(
        (
            tmp_path / "sample_data" / "replays" / "home_services" / "HOME-001" / "tailor.json"
        ).read_text(encoding="utf-8")
    )
    good = json.loads(json.dumps(bad))
    _write_replay(tmp_path, "home_services", "HOME-001", "tailor.attempt2.json", good)
    bad["evidence"][0]["quote"] = "purple widgets"
    _write_replay(tmp_path, "home_services", "HOME-001", "tailor.json", bad)
    result = _run("home_services", "HOME-001", tmp_path)
    calls = _calls(tmp_path, result.run_dir.name)
    assert sum(1 for item in calls if item["actor"] == "tailor") == 2
    gates = [
        item
        for item in _events(tmp_path)
        if item["event_type"] == "gate" and item["run_id"] == result.run_dir.name
    ]
    assert any(item["status"] == "fail" for item in gates)


def _run(profile_id, prospect_id, root):
    profile = load_profile(profile_id)
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
    return run_prospect(profile, prospect, load_pipeline_config(), root)


def _events(root):
    path = root / "runs" / "flight_recorder.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _calls(root, run_id):
    return [
        item
        for item in _events(root)
        if item["event_type"] == "model_call" and item["run_id"] == run_id
    ]


def _copy_replay(root, profile_id, prospect_id):
    source = ROOT / "sample_data" / "replays" / profile_id / prospect_id
    dest = root / "sample_data" / "replays" / profile_id / prospect_id
    shutil.copytree(source, dest)


def _write_replay(root, profile_id, prospect_id, name, payload):
    path = root / "sample_data" / "replays" / profile_id / prospect_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
