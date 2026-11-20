"""ICP scores, tiers, and the draft threshold."""

from leadgen.loaders import load_prospects
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import Prospect
from leadgen.scoring import qualify, score


B2B_RANKED = [
    ("B2B-001", 100, "hot", True),
    ("B2B-002", 75, "hot", True),
    ("B2B-004", 75, "hot", True),
    ("B2B-003", 50, "warm", False),
    ("B2B-006", 0, "cold", False),
]
HOME_RANKED = [
    ("HOME-001", 100, "hot", True),
    ("HOME-004", 85, "hot", True),
    ("HOME-002", 75, "hot", True),
    ("HOME-006", 40, "warm", False),
    ("HOME-003", 25, "cold", False),
]


def test_b2b_scores_rank_and_draft_gate():
    ranked, excluded = _qualify("b2b_services")
    assert _rows(ranked) == B2B_RANKED
    assert {row.prospect_id for row in ranked if row.draft_eligible} == {
        "B2B-001",
        "B2B-002",
        "B2B-004",
    }
    assert [item.prospect_id for item in excluded] == ["B2B-005"]
    assert "B2B-005" not in [row.prospect_id for row in ranked]
    _matched_points_sum_to_total(ranked)


def test_home_scores_rank_and_draft_gate():
    ranked, excluded = _qualify("home_services")
    assert _rows(ranked) == HOME_RANKED
    assert {row.prospect_id for row in ranked if row.draft_eligible} == {
        "HOME-001",
        "HOME-002",
        "HOME-004",
    }
    assert [item.prospect_id for item in excluded] == ["HOME-005"]
    assert "HOME-005" not in [row.prospect_id for row in ranked]
    _matched_points_sum_to_total(ranked)


def test_employee_count_bounds_are_inclusive():
    profile = load_profile("b2b_services")
    pipeline = load_pipeline_config()
    for count, matched in ((10, True), (200, True), (9, False), (201, False)):
        result = score(_edge(employee_count=count), profile, pipeline)
        hit = next(item for item in result.rule_hits if item.field == "employee_count")
        assert hit.matched is matched


def test_last_engaged_days_max_is_inclusive():
    profile = load_profile("b2b_services")
    pipeline = load_pipeline_config()
    for days, matched in ((30, True), (31, False)):
        result = score(_edge(last_engaged_days=days), profile, pipeline)
        hit = next(item for item in result.rule_hits if item.field == "last_engaged_days")
        assert hit.matched is matched


def _qualify(profile_id):
    profile = load_profile(profile_id)
    return qualify(load_prospects(profile), profile, load_pipeline_config())


def _rows(ranked):
    return [
        (row.prospect_id, row.total, row.tier, row.draft_eligible) for row in ranked
    ]


def _matched_points_sum_to_total(ranked):
    for row in ranked:
        matched = sum(hit.points for hit in row.rule_hits if hit.matched)
        assert matched == row.total


def _edge(employee_count=18, last_engaged_days=90):
    return Prospect(
        prospect_id="P-EDGE",
        profile_id="sample",
        contact_name="Edge Case",
        organization="Edge Co",
        email="edge@example.com",
        region="Mesa",
        source="cold_list",
        last_engaged_days=last_engaged_days,
        consent_status="opt_in",
        do_not_contact=False,
        notes="Boundary check.",
        attributes={
            "employee_count": employee_count,
            "industry": "retail",
            "current_it_setup": "other_msp",
        },
    )
