"""Shared test helper: put Acme search hits on the shortlist."""

from datetime import date
from pathlib import Path

from leadgen.profiles import load_profile
from leadgen.search import search
from leadgen.shortlist import add_shortlist
from leadgen.ui_data import search_view


def seed_shortlist(root: Path, limit: int | None = None) -> list[dict]:
    profile = load_profile("acme_plumbing")
    cities = [city for metro in profile.search.metros for city in metro.cities]
    outcome = search(profile, "", root, today=date(2026, 11, 21), network=False, chosen_cities=cities)
    view = search_view(outcome)
    prospects = {item["prospect_id"]: item for item in view["prospects"]}
    rows = [
        {**row, "profile_id": profile.profile_id, "prospect": prospects[row["prospect_id"]]["prospect"]}
        for row in view["rows"]
    ]
    return add_shortlist(root, rows[:limit] if limit else rows)
