"""Disk cache for public-record responses. The key and the user agent are not stored."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from leadgen.llm import scrub


def cache_file(root: Path, source: str, material: str) -> Path:
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return root / "runs" / "source_cache" / source / f"{digest}.json"


def read_cache(path: Path, hours: int, now: datetime | None = None) -> str | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    stored = datetime.fromisoformat(payload["stored_at"])
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current - stored > timedelta(hours=hours):
        return None
    return str(payload["body"])


def write_cache(path: Path, body: str, now: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stored_at": (now or datetime.now(timezone.utc)).isoformat(),
        "body": scrub(body),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
