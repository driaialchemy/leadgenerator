"""Businesses a person added from Find. The file survives a refresh."""

import json
from pathlib import Path


def load_shortlist(root: Path) -> list[dict]:
    path = Path(root) / "runs" / "shortlist.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict) and row.get("prospect_id")]


def add_shortlist(root: Path, rows: list[dict]) -> list[dict]:
    current = load_shortlist(root)
    seen = {row["prospect_id"] for row in current}
    for row in rows:
        prospect_id = row.get("prospect_id")
        if prospect_id and prospect_id not in seen:
            current.append(row)
            seen.add(prospect_id)
    path = Path(root) / "runs" / "shortlist.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current
