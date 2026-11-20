"""Append-only logbook. Lines are added and never rewritten."""

from pathlib import Path

from leadgen.schemas import FlightEvent


def recorder_path(root: Path) -> Path:
    return root / "runs" / "flight_recorder.jsonl"


def append_event(event: FlightEvent, path: Path) -> None:
    """Add one JSON line. Existing bytes are not touched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = event.model_dump_json() + "\n"
    with path.open("ab") as handle:
        handle.write(line.encode("utf-8"))
