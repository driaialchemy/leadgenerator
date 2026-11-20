"""Synthetic prospects and past outcomes."""

import csv
from collections import Counter
from pathlib import Path

import pytest

from leadgen.loaders import load_outcomes, load_prospects
from leadgen.profiles import load_profile

ROOT = Path(__file__).resolve().parents[1]


def test_each_profile_has_six_unique_prospects():
    for profile_id in ("b2b_services", "home_services"):
        prospects = load_prospects(load_profile(profile_id))
        assert len(prospects) == 6
        ids = [prospect.prospect_id for prospect in prospects]
        assert len(ids) == len(set(ids))


def test_attributes_match_the_profile():
    for profile_id in ("b2b_services", "home_services"):
        profile = load_profile(profile_id)
        for prospect in load_prospects(profile):
            assert set(prospect.attributes) == set(profile.attributes)
            for name, kind in profile.attributes.items():
                value = prospect.attributes[name]
                if kind == "int":
                    assert type(value) is int
                else:
                    assert type(value) is str


def test_home_organizations_are_blank():
    prospects = load_prospects(load_profile("home_services"))
    assert [prospect.organization for prospect in prospects] == [None] * 6


def test_extra_column_is_rejected(tmp_path):
    profile = load_profile("b2b_services")
    source = ROOT / "sample_data" / "b2b_services" / "prospects.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or []) + ["favorite_color"]
    path = tmp_path / "prospects.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row["favorite_color"] = "blue"
            writer.writerow(row)
    with pytest.raises(ValueError, match="favorite_color"):
        load_prospects(profile, path)


def test_emails_are_example_com():
    for profile_id in ("b2b_services", "home_services"):
        for prospect in load_prospects(load_profile(profile_id)):
            assert prospect.email.endswith("@example.com")


@pytest.mark.parametrize(
    ("profile_id", "won_values", "stages"),
    [
        (
            "b2b_services",
            [18000, 24000],
            {
                "won": 2,
                "lost_after_meeting": 1,
                "meeting": 1,
                "replied": 2,
                "sent": 2,
            },
        ),
        (
            "home_services",
            [9500, 7200, 350],
            {
                "won": 3,
                "lost_after_meeting": 1,
                "meeting": 0,
                "replied": 1,
                "sent": 3,
            },
        ),
    ],
)
def test_outcomes(profile_id, won_values, stages):
    outcomes = load_outcomes(load_profile(profile_id))
    assert len(outcomes) == 8
    won = [item.deal_value for item in outcomes if item.furthest_stage == "won"]
    assert won == won_values
    assert sum(won) == sum(won_values)
    counts = Counter(item.furthest_stage for item in outcomes)
    for stage, count in stages.items():
        assert counts[stage] == count
