"""Write one approved message as a file. This does not send it."""

import json
from pathlib import Path


def write_outbox(run_dir: Path, root: Path) -> Path:
    """Re-read the approval from disk, then write outbox/<run_id>.txt once."""
    approval = json.loads((run_dir / "approval.json").read_text(encoding="utf-8"))
    if approval["decision"] not in {"APPROVED", "EDITED"}:
        raise RuntimeError("Only an approved decision can be written to the outbox.")
    body = (run_dir / "rendered.txt").read_text(encoding="utf-8")
    dest_dir = root / "outbox"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{run_dir.name}.txt"
    if dest.exists():
        raise FileExistsError(f"{dest.name} is already in the outbox.")
    dest.write_text(body, encoding="utf-8")
    return dest
