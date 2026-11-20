"""Shape scores, runs, and the logbook for the class page. No layout here."""

import json
import os
from pathlib import Path

from leadgen.findings import run_note_checks
from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.llm import current_mode, role_config
from leadgen.loaders import load_outcomes, load_prospects
from leadgen.metrics import funnel
from leadgen.paths import repo_root
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.scoring import qualify


def markdown_table(rows: list[dict], columns: list[str]) -> str:
    """A plain table the page can show in large type."""
    if not rows:
        return "None."
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, rule]
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if value is None:
                value = ""
            cells.append(str(value).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def data_root() -> Path:
    """Where this session writes runs and the outbox."""
    raw = os.environ.get("LEADGEN_DATA_ROOT", "").strip()
    if raw:
        return Path(raw)
    return repo_root()


def profile_ids() -> list[str]:
    folder = repo_root() / "config" / "profiles"
    return sorted(path.stem for path in folder.glob("*.yaml"))


def kill_message(root: Path | None = None) -> str:
    folder = data_root() if root is None else Path(root)
    try:
        assert_not_engaged(folder)
    except KillSwitchEngaged as exc:
        return str(exc)
    return ""


def role_rows() -> list[dict]:
    mode = current_mode()
    rows = []
    for role in ("tailor", "drafter", "evaluator"):
        provider, model, _key_name = role_config(role)
        rows.append({"role": role, "provider": provider, "model": model, "mode": mode})
    return rows


def prospect_board(profile_id: str) -> dict:
    profile = load_profile(profile_id)
    pipeline = load_pipeline_config()
    prospects = load_prospects(profile)
    ranked, excluded = qualify(prospects, profile, pipeline)
    findings = []
    for prospect in sorted(prospects, key=lambda item: item.prospect_id):
        for finding in run_note_checks(prospect, profile):
            findings.append(finding.model_dump())
    rows = [
        {
            "prospect_id": row.prospect_id,
            "score": row.total,
            "tier": row.tier,
            "draft_eligible": row.draft_eligible,
            "rule_hits": [hit.model_dump() for hit in row.rule_hits],
        }
        for row in ranked
    ]
    return {
        "ranked": rows,
        "excluded": [
            {"prospect_id": item.prospect_id, "reason": item.reason} for item in excluded
        ],
        "findings": findings,
        "eligible_ids": [row["prospect_id"] for row in rows if row["draft_eligible"]],
    }


def funnel_view(profile_id: str) -> dict:
    profile = load_profile(profile_id)
    return funnel(load_outcomes(profile)).model_dump()


def attempt_comparison(run_dir: Path) -> list[dict]:
    rows = []
    paths = sorted(Path(run_dir).glob("verification.attempt*.json"))
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        report = payload["report"]
        number = int(path.stem.replace("verification.attempt", ""))
        draft_path = Path(run_dir) / f"draft.attempt{number}.json"
        draft = {}
        if draft_path.is_file():
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "attempt": number,
                "passed": report["passed"],
                "codes": [issue["code"] for issue in report["blocking"]],
                "hook": draft.get("hook", ""),
                "bridge": draft.get("bridge", ""),
            }
        )
    return rows


def logbook(root: Path, run_id: str) -> list[dict]:
    path = Path(root) / "runs" / "flight_recorder.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("run_id") != run_id:
            continue
        rows.append(
            {
                "event_type": event.get("event_type"),
                "attempt_number": event.get("attempt_number"),
                "retry_of": event.get("retry_of"),
                "retry_reason": event.get("retry_reason"),
                "red_team": event.get("red_team", False),
                "provider": event.get("provider"),
                "model": event.get("model"),
                "duration_ms": event.get("duration_ms"),
                "run_id": event.get("run_id"),
                "actor": event.get("actor"),
                "status": event.get("status"),
                "detail": event.get("detail"),
            }
        )
    return rows


def outbox_rows(root: Path) -> list[dict]:
    folder = Path(root) / "outbox"
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.glob("*.txt")):
        approval = Path(root) / "runs" / path.stem / "approval.json"
        name = ""
        if approval.is_file():
            name = json.loads(approval.read_text(encoding="utf-8")).get("name", "")
        rows.append(
            {
                "file": path.name,
                "approver": name,
                "text": path.read_text(encoding="utf-8"),
            }
        )
    return rows


def rendered_text(run_dir: Path) -> str:
    path = Path(run_dir) / "rendered.txt"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def run_status(run_dir: Path) -> dict:
    return json.loads((Path(run_dir) / "status.json").read_text(encoding="utf-8"))


def evaluation_view(run_dir: Path) -> dict | None:
    path = Path(run_dir) / "evaluation.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["bar"] = load_pipeline_config().evaluator_pass_score
    return data


def draft_fields(run_dir: Path) -> dict:
    data = json.loads((Path(run_dir) / "draft.json").read_text(encoding="utf-8"))
    return {"hook": data.get("hook", ""), "bridge": data.get("bridge", "")}
