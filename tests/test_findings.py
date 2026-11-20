"""Note checks are shown to a person. They do not block."""

from leadgen.findings import run_note_checks
from leadgen.loaders import load_prospects
from leadgen.profiles import load_profile

EXPECTED = {
    "b2b_services": {
        "B2B-001": ["pricing_question"],
        "B2B-002": [],
        "B2B-003": [],
        "B2B-004": ["headcount_change"],
        "B2B-005": [],
        "B2B-006": [],
    },
    "home_services": {
        "HOME-001": [],
        "HOME-002": ["pricing_question"],
        "HOME-003": [],
        "HOME-004": ["pricing_question", "system_age_conflict"],
        "HOME-005": [],
        "HOME-006": [],
    },
}


def test_findings_match_the_notes():
    for profile_id, expected in EXPECTED.items():
        profile = load_profile(profile_id)
        for prospect in load_prospects(profile):
            found = [item.check_id for item in run_note_checks(prospect, profile)]
            assert found == expected[prospect.prospect_id]


def test_young_system_drops_the_age_conflict():
    profile = load_profile("home_services")
    prospect = next(
        item
        for item in load_prospects(profile)
        if item.prospect_id == "HOME-004"
    )
    younger = prospect.model_copy(
        update={"attributes": {**prospect.attributes, "system_age_years": 1}}
    )
    found = [item.check_id for item in run_note_checks(younger, profile)]
    assert found == ["pricing_question"]
