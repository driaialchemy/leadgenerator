"""Clear everything a person has worked on, except their details, connections, and the logbook."""

import shutil
from pathlib import Path

KEEP_IN_RUNS = {"sender.json", "flight_recorder.jsonl", ".gitkeep", "source_cache"}


def clear_everything(root: Path) -> dict[str, int]:
    """Remove searches, drafts, approvals, and Practice sends. Returns what was removed."""
    removed = {"runs": 0, "files": 0, "outbox": 0}
    runs = Path(root) / "runs"
    if runs.is_dir():
        for item in runs.iterdir():
            if item.name in KEEP_IN_RUNS or item.name.startswith("kill"):
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed["runs"] += 1
            elif item.suffix == ".json":
                item.unlink(missing_ok=True)
                removed["files"] += 1
    outbox = Path(root) / "outbox"
    if outbox.is_dir():
        for item in outbox.iterdir():
            if item.is_file() and item.name != ".gitkeep":
                item.unlink(missing_ok=True)
                removed["outbox"] += 1
    return removed
