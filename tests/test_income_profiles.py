"""Three income-model profiles. Expected numbers are hand-counted from the CSVs."""

import json

from leadgen.findings import run_note_checks
from leadgen.loaders import load_outcomes, load_prospects
from leadgen.metrics import funnel
from leadgen.phrases import is_banned
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.scoring import qualify
from leadgen.ui_data import profile_ids

RANKED = {
    "ai_automation_services": [
        ("AUTO-001", 100, "hot", True),
        ("AUTO-002", 100, "hot", True),
        ("AUTO-003", 75, "hot", True),
        ("AUTO-004", 55, "warm", False),
        ("AUTO-006", 0, "cold", False),
    ],
    "admin_assist_services": [
        ("ADMN-001", 100, "hot", True),
        ("ADMN-002", 100, "hot", True),
        ("ADMN-003", 75, "hot", True),
        ("ADMN-004", 50, "warm", False),
        ("ADMN-006", 0, "cold", False),
    ],
    "newsletter_sponsorships": [
        ("NEWS-001", 100, "hot", True),
        ("NEWS-002", 100, "hot", True),
        ("NEWS-003", 90, "hot", True),
        ("NEWS-004", 50, "warm", False),
        ("NEWS-006", 0, "cold", False),
    ],
}
EXCLUDED = {
    "ai_automation_services": [("AUTO-005", "do_not_contact")],
    "admin_assist_services": [("ADMN-005", "no_consent")],
    "newsletter_sponsorships": [("NEWS-005", "do_not_contact")],
}
DRAFTABLE = {
    "ai_automation_services": {"AUTO-001", "AUTO-002", "AUTO-003"},
    "admin_assist_services": {"ADMN-001", "ADMN-002", "ADMN-003"},
    "newsletter_sponsorships": {"NEWS-001", "NEWS-002", "NEWS-003"},
}
FINDINGS = {
    "ai_automation_services": {"AUTO-003": ["guarantee_ask"]},
    "admin_assist_services": {"ADMN-003": ["guarantee_ask"]},
    "newsletter_sponsorships": {"NEWS-003": ["guarantee_ask"]},
}
FUNNELS = {
    "ai_automation_services": {
        "sent": 8,
        "replied": 6,
        "meeting": 4,
        "won": 2,
        "won_value": 4200,
        "reply_rate": 0.75,
        "meeting_rate": 0.5,
        "win_rate": 0.25,
        "avg_deal": 2100.00,
    },
    "admin_assist_services": {
        "sent": 8,
        "replied": 5,
        "meeting": 4,
        "won": 3,
        "won_value": 1950,
        "reply_rate": 0.625,
        "meeting_rate": 0.5,
        "win_rate": 0.375,
        "avg_deal": 650.00,
    },
    "newsletter_sponsorships": {
        "sent": 8,
        "replied": 6,
        "meeting": 4,
        "won": 2,
        "won_value": 800,
        "reply_rate": 0.75,
        "meeting_rate": 0.5,
        "win_rate": 0.25,
        "avg_deal": 400.00,
    },
}
CAUGHT = {
    ("ai_automation_services", "AUTO-002"): "passive income",
    ("admin_assist_services", "ADMN-002"): "make money",
    ("newsletter_sponsorships", "NEWS-002"): "double your revenue",
}
CLEAN = (
    ("ai_automation_services", "AUTO-001", []),
    ("ai_automation_services", "AUTO-003", ["guarantee_ask"]),
    ("admin_assist_services", "ADMN-001", []),
    ("admin_assist_services", "ADMN-003", ["guarantee_ask"]),
    ("newsletter_sponsorships", "NEWS-001", []),
    ("newsletter_sponsorships", "NEWS-003", ["guarantee_ask"]),
)


def test_profiles_load_and_points_sum_to_100():
    for profile_id in RANKED:
        profile = load_profile(profile_id)
        assert profile.profile_id == profile_id
        assert sum(rule.points for rule in profile.scoring_rules) == 100
        assert "$" in profile.banned_phrases
        assert "%" in profile.banned_phrases
        texts = [*profile.approved_claims.values(), *profile.approved_subjects.values(), profile.cta]
        for text in texts:
            for phrase in profile.banned_phrases:
                assert is_banned(text, phrase) is False


def test_hand_counted_scores_tiers_and_exclusions():
    for profile_id, expected in RANKED.items():
        ranked, excluded = qualify(
            load_prospects(load_profile(profile_id)),
            load_profile(profile_id),
            load_pipeline_config(),
        )
        assert [
            (row.prospect_id, row.total, row.tier, row.draft_eligible) for row in ranked
        ] == expected
        assert {row.prospect_id for row in ranked if row.draft_eligible} == DRAFTABLE[profile_id]
        assert [(item.prospect_id, item.reason) for item in excluded] == EXCLUDED[profile_id]


def test_hand_counted_findings():
    for profile_id, expected in FINDINGS.items():
        profile = load_profile(profile_id)
        found = {}
        for prospect in load_prospects(profile):
            checks = [item.check_id for item in run_note_checks(prospect, profile)]
            if checks:
                found[prospect.prospect_id] = checks
        assert found == expected


def test_hand_counted_funnels():
    for profile_id, expected in FUNNELS.items():
        stats = funnel(load_outcomes(load_profile(profile_id)))
        assert stats.model_dump() == expected


def test_caught_replay_blocks_then_reaches_approval(tmp_path):
    pipeline = load_pipeline_config()
    for (profile_id, prospect_id), phrase in CAUGHT.items():
        profile = load_profile(profile_id)
        prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
        result = run_prospect(profile, prospect, pipeline, tmp_path)
        attempt1 = json.loads(
            (result.run_dir / "verification.attempt1.json").read_text(encoding="utf-8")
        )
        messages = [item["message"] for item in attempt1["report"]["blocking"]]
        assert any(phrase in message for message in messages)
        assert result.status == "PENDING_APPROVAL"


def test_other_drafts_pass_on_the_first_attempt(tmp_path):
    pipeline = load_pipeline_config()
    for profile_id, prospect_id, findings in CLEAN:
        profile = load_profile(profile_id)
        prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
        result = run_prospect(profile, prospect, pipeline, tmp_path)
        status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
        assert result.status == "PENDING_APPROVAL"
        assert [item["check_id"] for item in status["findings"]] == findings
        assert not (result.run_dir / "verification.attempt2.json").exists()


def test_picker_keeps_the_original_default_first():
    assert profile_ids() == [
        "b2b_services",
        "home_services",
        "admin_assist_services",
        "ai_automation_services",
        "newsletter_sponsorships",
    ]
