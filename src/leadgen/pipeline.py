"""One prospect: tailor, draft, verify, evaluate, and at most one retry."""

import contextvars
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from leadgen.exclusions import apply_exclusions
from leadgen.findings import run_note_checks
from leadgen.flight_recorder import append_event, recorder_path
from leadgen.gates import check_tailor
from leadgen.kill_switch import assert_not_engaged
from leadgen.llm import complete, current_mode, scrub
from leadgen.messages import (
    drafter_prompt,
    evaluator_prompt,
    format_rendered,
    tailor_prompt,
)
from leadgen.paths import repo_root
from leadgen.renderer import render
from leadgen.schemas import (
    DraftEmail,
    EvaluatorResult,
    Finding,
    FlightEvent,
    PipelineConfig,
    Profile,
    Prospect,
    TailorResult,
    VerifyReport,
)
from leadgen.scoring import score
from leadgen.verifier import verify

_PROGRESS: contextvars.ContextVar = contextvars.ContextVar("leadgen_progress", default=None)


def _emit(payload: dict) -> None:
    callback = _PROGRESS.get()
    if callback is not None:
        callback(payload)


class RunResult:
    def __init__(self, status: str, run_dir: Path | None):
        self.status = status
        self.run_dir = run_dir


class _Budget:
    def __init__(self, root: Path, run_id: str):
        self.root = root
        self.run_id = run_id
        self.used = False

    def spend(self, role: str, reason: str) -> bool:
        if self.used:
            return False
        self.used = True
        _log(
            self.root,
            self.run_id,
            "retry",
            role,
            "ok",
            reason,
            attempt_number=2,
            retry_of=role,
            retry_reason=reason,
        )
        _emit({"stage": "retry", "role": role, "passed": False, "detail": reason, "attempt": 2})
        return True


def run_prospect(
    profile: Profile,
    prospect: Prospect,
    pipeline: PipelineConfig,
    root: Path | None = None,
    on_progress=None,
) -> RunResult:
    """Refuse ineligible prospects before any prompt. Otherwise run one folder."""
    token = _PROGRESS.set(on_progress)
    try:
        return _run_prospect(profile, prospect, pipeline, root)
    finally:
        _PROGRESS.reset(token)


def _run_prospect(
    profile: Profile, prospect: Prospect, pipeline: PipelineConfig, root: Path | None
) -> RunResult:
    folder = Path(root) if root is not None else repo_root()
    assert_not_engaged(folder)
    _eligible, excluded = apply_exclusions([prospect], pipeline)
    below = excluded or not score(prospect, profile, pipeline).draft_eligible
    if below:
        _log(
            folder,
            prospect.prospect_id,
            "refusal",
            "system",
            "blocked",
            f"{prospect.prospect_id} was not sent to a model.",
        )
        return RunResult("REFUSED", None)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{prospect.prospect_id}-{stamp}"
    run_dir = folder / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prospect.json").write_text(
        prospect.model_dump_json(indent=2), encoding="utf-8"
    )
    budget = _Budget(folder, run_id)
    findings = run_note_checks(prospect, profile)

    tailor, gate_failed = _tailor_pass(folder, run_dir, profile, prospect, pipeline, budget)
    if tailor is None:
        _finish(run_dir, prospect, profile, "BLOCKED", False, findings)
        return RunResult("BLOCKED", run_dir)

    attempt = 1
    feedback = None
    while True:
        draft = _draft_pass(folder, run_dir, profile, prospect, tailor, attempt, feedback)
        report = _verify_pass(folder, run_dir, profile, prospect, pipeline, tailor, draft, attempt)
        findings = report.findings
        if not report.passed:
            reason = "; ".join(issue.message for issue in report.blocking)
            if not budget.spend("drafter", reason):
                _finish(run_dir, prospect, profile, "BLOCKED", False, findings)
                return RunResult("BLOCKED", run_dir)
            attempt += 1
            feedback = reason
            continue
        low = _eval_pass(folder, run_dir, profile, prospect, pipeline)
        if low:
            if not budget.spend("drafter", low):
                _finish(run_dir, prospect, profile, "PENDING_APPROVAL", True, findings)
                return RunResult("PENDING_APPROVAL", run_dir)
            attempt += 1
            feedback = low
            continue
        _finish(run_dir, prospect, profile, "PENDING_APPROVAL", False, findings)
        return RunResult("PENDING_APPROVAL", run_dir)


def _tailor_pass(folder, run_dir, profile, prospect, pipeline, budget):
    tailor = _call_tailor(folder, run_dir, profile, prospect, attempt=1, feedback=None)
    issues = _gate(folder, run_dir, profile, prospect, pipeline, tailor)
    if not issues:
        return tailor, False
    reason = "; ".join(issue.message for issue in issues)
    if not budget.spend("tailor", reason):
        return None, True
    tailor = _call_tailor(folder, run_dir, profile, prospect, attempt=2, feedback=reason)
    issues = _gate(folder, run_dir, profile, prospect, pipeline, tailor)
    if issues:
        return None, True
    return tailor, False


def _call_tailor(folder, run_dir, profile, prospect, attempt, feedback) -> TailorResult:
    prompt = tailor_prompt(prospect, profile, feedback)
    text = _model_call(
        folder, run_dir, "tailor", prompt, profile.profile_id, prospect.prospect_id, attempt
    )
    parsed = TailorResult.model_validate_json(text)
    _write_json(run_dir / "tailor.json", parsed)
    _write_json(run_dir / f"tailor.attempt{attempt}.json", parsed)
    return TailorResult.model_validate_json((run_dir / "tailor.json").read_text(encoding="utf-8"))


def _gate(folder, run_dir, profile, prospect, pipeline, tailor):
    fresh = TailorResult.model_validate_json((run_dir / "tailor.json").read_text(encoding="utf-8"))
    issues = check_tailor(fresh, prospect, profile, pipeline)
    _log(
        folder,
        run_dir.name,
        "gate",
        "tailor",
        "ok" if not issues else "fail",
        "; ".join(issue.message for issue in issues) or "Claims and evidence passed.",
        output_path=(run_dir / "tailor.json").as_posix(),
    )
    detail = "; ".join(issue.message for issue in issues) or "Claims and evidence passed."
    _emit({"stage": "gate", "role": "tailor", "passed": not issues, "detail": detail})
    return issues


def _draft_pass(folder, run_dir, profile, prospect, tailor, attempt, feedback) -> DraftEmail:
    prompt = drafter_prompt(prospect, profile, tailor, feedback, attempt=attempt)
    text = _model_call(
        folder, run_dir, "drafter", prompt, profile.profile_id, prospect.prospect_id, attempt
    )
    parsed = DraftEmail.model_validate_json(text)
    _write_json(run_dir / "draft.json", parsed)
    _write_json(run_dir / f"draft.attempt{attempt}.json", parsed)
    fresh = DraftEmail.model_validate_json((run_dir / "draft.json").read_text(encoding="utf-8"))
    rendered = render(fresh, prospect, profile)
    rendered_text = format_rendered(rendered.subject, rendered.body)
    (run_dir / "rendered.txt").write_text(rendered_text, encoding="utf-8")
    return fresh


def _verify_pass(folder, run_dir, profile, prospect, pipeline, tailor, draft, attempt) -> VerifyReport:
    fresh_tailor = TailorResult.model_validate_json((run_dir / "tailor.json").read_text(encoding="utf-8"))
    fresh_draft = DraftEmail.model_validate_json((run_dir / "draft.json").read_text(encoding="utf-8"))
    report = verify(fresh_tailor, fresh_draft, prospect, profile, pipeline)
    draft_text = (run_dir / "draft.json").read_text(encoding="utf-8")
    payload = {
        "draft_sha256": hashlib.sha256(draft_text.encode("utf-8")).hexdigest(),
        "report": report.model_dump(mode="json"),
    }
    raw = json.dumps(payload, indent=2)
    (run_dir / f"verification.attempt{attempt}.json").write_text(raw, encoding="utf-8")
    (run_dir / "verification.json").write_text(raw, encoding="utf-8")
    codes = ", ".join(issue.code for issue in report.blocking) or "passed"
    _log(
        folder,
        run_dir.name,
        "verifier",
        "verifier",
        "ok" if report.passed else "fail",
        codes,
        output_path=(run_dir / "verification.json").as_posix(),
        attempt_number=attempt,
    )
    _emit(
        {
            "stage": "verifier",
            "role": "verifier",
            "passed": report.passed,
            "detail": codes,
            "attempt": attempt,
        }
    )
    return report


def _eval_pass(folder, run_dir, profile, prospect, pipeline) -> str:
    """Return the retry reason when any score is under the bar, else an empty string."""
    existing = list(run_dir.glob("evaluation.attempt*.json"))
    attempt = len(existing) + 1
    rendered = (run_dir / "rendered.txt").read_text(encoding="utf-8")
    prompt = evaluator_prompt(profile.buyer_persona, rendered)
    text = _model_call(
        folder, run_dir, "evaluator", prompt, profile.profile_id, prospect.prospect_id, attempt
    )
    parsed = EvaluatorResult.model_validate_json(text)
    _write_json(run_dir / "evaluation.json", parsed)
    _write_json(run_dir / f"evaluation.attempt{attempt}.json", parsed)
    fresh = EvaluatorResult.model_validate_json((run_dir / "evaluation.json").read_text(encoding="utf-8"))
    low = _low_scores(fresh, pipeline)
    _log(
        folder,
        run_dir.name,
        "evaluator",
        "evaluator",
        "ok" if not low else "fail",
        low or "Every score is at or above the bar.",
        output_path=(run_dir / "evaluation.json").as_posix(),
        attempt_number=attempt,
    )
    _emit(
        {
            "stage": "evaluator",
            "role": "evaluator",
            "passed": not low,
            "detail": low or "Every score is at or above the bar.",
            "attempt": attempt,
        }
    )
    return low


def _low_scores(result: EvaluatorResult, pipeline: PipelineConfig) -> str:
    parts = []
    bar = pipeline.evaluator_pass_score
    for name in ("relevance", "specificity", "clarity", "tone"):
        value = getattr(result, name)
        if value < bar:
            parts.append(f"{name} is {value}, below {bar}")
    if not parts:
        return ""
    if result.suggestions:
        parts.append("Suggestions: " + " ".join(result.suggestions))
    return "; ".join(parts)


def _model_call(folder, run_dir, role, prompt, profile_id, prospect_id, attempt) -> str:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    result = complete(role, prompt, profile_id, prospect_id, attempt, folder)
    _log(
        folder,
        run_dir.name,
        "model_call",
        role,
        "ok",
        role,
        attempt_number=attempt,
        input_sha256=digest,
        provider=result.provider,
        model=result.model,
        duration_ms=result.duration_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        red_team=result.red_team,
    )
    seconds = None if result.duration_ms is None else round(result.duration_ms / 1000, 1)
    _emit(
        {
            "stage": "model_call",
            "role": role,
            "provider": result.provider,
            "model": result.model,
            "seconds": seconds,
            "passed": True,
            "detail": role,
            "attempt": attempt,
        }
    )
    return result.text


def _finish(run_dir, prospect, profile, status, below, findings: list[Finding]) -> None:
    payload = {
        "prospect_id": prospect.prospect_id,
        "profile_id": profile.profile_id,
        "status": status,
        "evaluator_below_bar": below,
        "findings": [item.model_dump(mode="json") for item in findings],
    }
    (run_dir / "status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_json(path: Path, model) -> None:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _log(
    root: Path,
    run_id: str,
    event_type: str,
    actor: str,
    status: str,
    detail: str,
    **fields,
) -> None:
    mode = "offline"
    try:
        mode = current_mode()
    except Exception:
        mode = "offline"
    clean = {
        key: scrub(value) if isinstance(value, str) else value
        for key, value in fields.items()
    }
    event = FlightEvent(
        event_id=str(uuid4()),
        ts=datetime.now(timezone.utc).isoformat(),
        run_id=run_id,
        event_type=event_type,
        actor=actor,
        mode=mode,
        status=status,
        detail=scrub(detail),
        **clean,
    )
    append_event(event, recorder_path(root))
