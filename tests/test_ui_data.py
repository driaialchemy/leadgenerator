"""The page reads the same ranks, attempts, and logbook the pipeline writes."""

from leadgen.loaders import load_prospects
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.ui_data import attempt_comparison, logbook, prospect_board


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


def test_prospect_board_matches_ranking():
    b2b = prospect_board("b2b_services")
    assert _rows(b2b) == B2B_RANKED
    assert b2b["excluded"] == [{"prospect_id": "B2B-005", "reason": "do_not_contact"}]
    assert _finding_ids(b2b) == {
        ("B2B-001", "pricing_question"),
        ("B2B-004", "headcount_change"),
    }

    home = prospect_board("home_services")
    assert _rows(home) == HOME_RANKED
    assert home["excluded"] == [{"prospect_id": "HOME-005", "reason": "no_consent"}]
    assert _finding_ids(home) == {
        ("HOME-002", "pricing_question"),
        ("HOME-004", "pricing_question"),
        ("HOME-004", "system_age_conflict"),
    }


def test_attempt_comparison_lists_blocked_codes(tmp_path):
    result = _run(tmp_path, "b2b_services", "B2B-001")
    rows = attempt_comparison(result.run_dir)
    assert [row["attempt"] for row in rows] == [1, 2]
    blocked = next(row for row in rows if not row["passed"])
    assert set(blocked["codes"]) == {"raw_fact", "digits", "banned_phrase"}


def test_logbook_keeps_one_run_and_the_retry(tmp_path):
    first = _run(tmp_path, "b2b_services", "B2B-001")
    second = _run(tmp_path, "b2b_services", "B2B-002")
    rows = logbook(tmp_path, first.run_dir.name)
    assert rows
    assert {row["run_id"] for row in rows} == {first.run_dir.name}
    assert second.run_dir.name not in {row["run_id"] for row in rows}
    retry = next(row for row in rows if row["event_type"] == "retry")
    assert retry["attempt_number"] == 2
    assert retry["retry_of"]
    assert retry["retry_reason"]
    assert "provider" in retry
    assert "model" in retry
    assert "duration_ms" in retry
    assert "red_team" in retry


def _rows(board):
    return [
        (row["prospect_id"], row["score"], row["tier"], row["draft_eligible"])
        for row in board["ranked"]
    ]


def _finding_ids(board):
    return {(row["prospect_id"], row["check_id"]) for row in board["findings"]}


def _run(root, profile_id, prospect_id):
    profile = load_profile(profile_id)
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
    return run_prospect(profile, prospect, load_pipeline_config(), root)

