"""A named person signs a finished run. Send means one file in the outbox."""

import argparse
import hashlib
import json
from pathlib import Path

from leadgen.kill_switch import KillSwitchEngaged, assert_not_engaged
from leadgen.loaders import load_prospects
from leadgen.messages import format_rendered
from leadgen.outbox import write_outbox
from leadgen.paths import repo_root
from leadgen.pipeline import _log
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.renderer import render
from leadgen.schemas import ApprovalRecord, DraftEmail, TailorResult
from leadgen.verifier import verify


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m leadgen.approve")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--prospect", required=True)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--name", required=True)
    parser.add_argument("--decision", required=True, choices=["APPROVED", "EDITED", "REJECTED"])
    parser.add_argument("--ack-findings", action="store_true")
    parser.add_argument("--hook")
    parser.add_argument("--bridge")
    args = parser.parse_args(argv)
    folder = Path(root) if root is not None else repo_root()
    code, message = decide(
        folder,
        args.profile,
        args.prospect,
        args.decision,
        args.name,
        args.ack_findings,
        args.hook,
        args.bridge,
    )
    if message:
        print(message)
    return code


def decide(
    root: Path,
    profile_id: str,
    prospect_id: str,
    decision: str,
    name: str,
    ack_findings: bool = False,
    hook: str | None = None,
    bridge: str | None = None,
) -> tuple[int, str]:
    """Apply one approval decision. The CLI prints the returned message."""
    folder = Path(root) if root is not None else repo_root()
    try:
        assert_not_engaged(folder)
    except KillSwitchEngaged as exc:
        _log(folder, "kill-switch", "kill_switch_block", "system", "blocked", str(exc))
        return 1, str(exc)
    try:
        run_dir = latest_run(folder, prospect_id)
    except FileNotFoundError as exc:
        return 1, str(exc)
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    if status["profile_id"] != profile_id:
        return 1, "That run is for a different profile."
    if status["status"] == "BLOCKED":
        return 1, "BLOCKED runs cannot be approved."
    if not name.strip():
        return 1, "A name is required."
    if status["findings"] and not ack_findings:
        return 1, "Findings must be acknowledged."
    if (run_dir / "approval.json").is_file():
        return 1, "This run was already decided."
    if decision == "EDITED":
        if not hook or not bridge:
            return 1, "An edit needs a hook and a bridge."
        if not _apply_edit(folder, run_dir, hook, bridge):
            return 1, "The edit failed verification."
    elif not _draft_still_verified(run_dir):
        return 1, "The draft on disk changed after verification."
    elif not _reverify(run_dir):
        return 1, "The draft on disk no longer passes verification."
    record = ApprovalRecord(
        decision=decision,
        name=name.strip(),
        ack_findings=ack_findings,
        run_id=run_dir.name,
    )
    (run_dir / "approval.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")
    _log(
        folder,
        run_dir.name,
        "approval",
        "human",
        "ok",
        f"{record.decision} by {record.name}",
    )
    if decision == "REJECTED":
        return 0, "Rejected. Nothing was written to the outbox."
    dest = write_outbox(run_dir, folder)
    _log(folder, run_dir.name, "outbox", "outbox", "ok", dest.name, output_path=dest.as_posix())
    return 0, f"Wrote {dest.name}"


def latest_run(root: Path, prospect_id: str) -> Path:
    runs = root / "runs"
    matches = [
        path
        for path in runs.iterdir()
        if path.is_dir() and path.name.startswith(prospect_id + "-")
    ] if runs.is_dir() else []
    if not matches:
        raise FileNotFoundError(f"No run for {prospect_id}.")
    return sorted(matches)[-1]


def _draft_still_verified(run_dir: Path) -> bool:
    verification = json.loads((run_dir / "verification.json").read_text(encoding="utf-8"))
    current = (run_dir / "draft.json").read_text(encoding="utf-8")
    digest = hashlib.sha256(current.encode("utf-8")).hexdigest()
    return digest == verification["draft_sha256"]


def _reverify(run_dir: Path) -> bool:
    report = _verify_disk(run_dir)
    return report.passed


def _apply_edit(root: Path, run_dir: Path, hook: str, bridge: str) -> bool:
    draft = DraftEmail.model_validate_json((run_dir / "draft.json").read_text(encoding="utf-8"))
    edited = draft.model_copy(update={"hook": hook, "bridge": bridge})
    if not _passes(run_dir, edited):
        return False
    (run_dir / "draft.json").write_text(edited.model_dump_json(indent=2), encoding="utf-8")
    _render_disk(run_dir, edited)
    draft_text = (run_dir / "draft.json").read_text(encoding="utf-8")
    report = _verify_disk(run_dir)
    payload = {
        "draft_sha256": hashlib.sha256(draft_text.encode("utf-8")).hexdigest(),
        "report": report.model_dump(mode="json"),
    }
    (run_dir / "verification.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def _passes(run_dir: Path, draft: DraftEmail) -> bool:
    return _verify_disk(run_dir, draft).passed


def _verify_disk(run_dir: Path, draft: DraftEmail | None = None):
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    profile = load_profile(status["profile_id"])
    pipeline = load_pipeline_config()
    prospect = next(
        item
        for item in load_prospects(profile)
        if item.prospect_id == status["prospect_id"]
    )
    tailor = TailorResult.model_validate_json((run_dir / "tailor.json").read_text(encoding="utf-8"))
    if draft is None:
        draft = DraftEmail.model_validate_json((run_dir / "draft.json").read_text(encoding="utf-8"))
    return verify(tailor, draft, prospect, profile, pipeline)


def _render_disk(run_dir: Path, draft: DraftEmail) -> None:
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    profile = load_profile(status["profile_id"])
    prospect = next(
        item
        for item in load_prospects(profile)
        if item.prospect_id == status["prospect_id"]
    )
    rendered = render(draft, prospect, profile)
    (run_dir / "rendered.txt").write_text(
        format_rendered(rendered.subject, rendered.body), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
