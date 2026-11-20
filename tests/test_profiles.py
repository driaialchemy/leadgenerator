"""Profile files and the shared pipeline config."""

import re
from pathlib import Path

import pytest
import yaml

from leadgen.phrases import is_banned
from leadgen.profiles import load_pipeline_config, load_profile

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\{\{([^{}]+)\}\}")
ALLOWED_TOKENS = {"organization", "contact_first_name"}
PROFILE_IDS = ("b2b_services", "home_services")


def test_both_profiles_load():
    loaded = [load_profile(profile_id) for profile_id in PROFILE_IDS]
    assert [profile.profile_id for profile in loaded] == list(PROFILE_IDS)


def test_scoring_points_sum_to_100():
    for profile_id in PROFILE_IDS:
        profile = load_profile(profile_id)
        assert sum(rule.points for rule in profile.scoring_rules) == 100


def test_points_must_sum_to_100(tmp_path):
    data = _b2b_data()
    data["scoring_rules"][0]["points"] -= 5
    path = _write_profile(tmp_path, data)
    with pytest.raises(ValueError, match="100"):
        load_profile(data["profile_id"], path)


def test_undeclared_field_is_rejected(tmp_path):
    data = _b2b_data()
    data["scoring_rules"][0]["field"] = "favorite_color"
    path = _write_profile(tmp_path, data)
    with pytest.raises(ValueError, match="favorite_color"):
        load_profile(data["profile_id"], path)


def test_range_rule_needs_a_bound(tmp_path):
    data = _b2b_data()
    rule = next(item for item in data["scoring_rules"] if item["type"] == "range")
    rule.pop("min", None)
    rule.pop("max", None)
    path = _write_profile(tmp_path, data)
    with pytest.raises(ValueError, match="min"):
        load_profile(data["profile_id"], path)


def test_claim_and_subject_ids_are_unique():
    for profile_id in PROFILE_IDS:
        profile = load_profile(profile_id)
        assert len(profile.approved_claims) == len(set(profile.approved_claims))
        assert len(profile.approved_subjects) == len(set(profile.approved_subjects))


def test_subject_tokens_are_limited():
    for profile_id in PROFILE_IDS:
        profile = load_profile(profile_id)
        for text in profile.approved_subjects.values():
            found = set(TOKEN.findall(text))
            assert found <= ALLOWED_TOKENS


def test_pipeline_config_loads():
    config = load_pipeline_config()
    assert config.draft_threshold == 60
    assert config.tiers.warm_min == 40
    assert config.tiers.hot_min == 70
    assert config.max_revisions == 1
    assert config.evaluator_pass_score == 4
    assert config.exclusions.do_not_contact_is is True
    assert config.exclusions.consent_status_is == ["none"]
    assert config.max_ai_words == 90
    assert config.max_claims == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"tiers": {"warm_min": 80, "hot_min": 70}},
        {"tiers": {"warm_min": 70, "hot_min": 70}},
        {"tiers": {"hot_min": 101}},
        {"tiers": {"warm_min": -1}},
        {"draft_threshold": 101},
        {"draft_threshold": -1},
        {"max_ai_words": 9},
        {"max_claims": 0},
    ],
)
def test_pipeline_config_rejects_bad_bounds(tmp_path, patch):
    data = yaml.safe_load((ROOT / "config" / "pipeline.yaml").read_text(encoding="utf-8"))
    for key, value in patch.items():
        if isinstance(value, dict):
            data[key].update(value)
        else:
            data[key] = value
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data, default_style='"'), encoding="utf-8")
    with pytest.raises(ValueError):
        load_pipeline_config(path)


def test_approved_text_has_no_banned_phrase():
    for profile_id in PROFILE_IDS:
        profile = load_profile(profile_id)
        texts = [*profile.approved_claims.values(), *profile.approved_subjects.values(), profile.cta]
        for text in texts:
            for phrase in profile.banned_phrases:
                assert is_banned(text, phrase) is False


def test_flag_when_needs_an_attribute(tmp_path):
    data = _b2b_data()
    data["note_checks"].append(
        {
            "id": "bad_check",
            "phrases": ["price"],
            "flag_when": {"min": 3},
            "message": "Missing attribute.",
        }
    )
    path = _write_profile(tmp_path, data)
    with pytest.raises(ValueError, match="attribute"):
        load_profile(data["profile_id"], path)


def _b2b_data():
    path = ROOT / "config" / "profiles" / "b2b_services.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_profile(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, default_style='"'), encoding="utf-8")
    return path
