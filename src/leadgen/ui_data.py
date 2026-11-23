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
    """Every profile file. menu_order keeps the original default first."""
    folder = repo_root() / "config" / "profiles"
    ranked = []
    for path in folder.glob("*.yaml"):
        profile = load_profile(path.stem)
        ranked.append((profile.menu_order, path.stem))
    ranked.sort()
    return [profile_id for _, profile_id in ranked]


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
    for role in ("tailor", "drafter", "evaluator", "translator", "reason"):
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
    try:
        outcomes = load_outcomes(profile)
    except FileNotFoundError:
        outcomes = []
    return funnel(outcomes).model_dump()


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


def summary_tiles(root: Path, profile_id: str, shown: int) -> list[dict]:
    """Five counts. A signed run is not still waiting."""
    from leadgen.shortlist import load_shortlist

    shortlisted = len([row for row in load_shortlist(root) if row.get("profile_id") == profile_id])
    waiting = 0
    approved = 0
    runs = Path(root) / "runs"
    if runs.is_dir():
        for folder in runs.iterdir():
            if not folder.is_dir() or not _run_belongs(folder, profile_id):
                continue
            approval = folder / "approval.json"
            if approval.is_file():
                try:
                    decision = json.loads(approval.read_text(encoding="utf-8")).get("decision")
                except json.JSONDecodeError:
                    decision = None
                if decision in {"APPROVED", "EDITED"}:
                    approved += 1
                continue
            status_path = folder / "status.json"
            if not status_path.is_file():
                continue
            try:
                status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
            except json.JSONDecodeError:
                status = None
            if status == "PENDING_APPROVAL":
                waiting += 1
    sent = len([row for row in outbox_rows(root) if _run_belongs(runs / Path(row["file"]).stem, profile_id)])
    return [
        {"label": "Businesses found", "value": shown, "tone": "found"},
        {"label": "Previous searches", "value": shortlisted, "tone": "shortlist"},
        {"label": "Drafts waiting", "value": waiting, "tone": "waiting"},
        {"label": "Approved", "value": approved, "tone": "approved"},
        {"label": "Sent", "value": sent, "tone": "sent"},
    ]


def _run_belongs(folder: Path, profile_id: str) -> bool:
    """Runs written for a profile that no longer exists are not counted."""
    path = folder / "status.json"
    if not path.is_file():
        return True
    try:
        owner = json.loads(path.read_text(encoding="utf-8")).get("profile_id")
    except json.JSONDecodeError:
        return True
    return not owner or owner == profile_id


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


def contact_channels(run_dir: Path) -> list[str]:
    """Channels saved with the run. An empty email is stated, not invented."""
    path = Path(run_dir) / "prospect.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = []
    name = str(data.get("contact_name") or "").strip()
    title = str(data.get("contact_title") or "").strip()
    if name:
        lines.append(f"Point of contact: {name}" + (f", {title}" if title else ""))
    address = str(data.get("mailing_address") or "").strip()
    if address:
        lines.append(f"Mailing address: {address}")
    phone = str(data.get("phone") or "").strip()
    if phone:
        lines.append(f"Phone: {phone}")
    if not str(data.get("email") or "").strip():
        lines.append("No email on record")
    return lines


def search_view(outcome) -> dict:
    """Summary, table rows, and the prospects the page can add."""
    from leadgen.industry import live_size_note, title_for
    from leadgen.sources.records import SOURCE_LABELS

    rows = []
    prospects = []
    for hit in outcome.hits:
        code = hit.record.naics[0] if hit.record.naics else ""
        count = hit.record.employee_count
        rows.append(
            {
                "business": hit.business_name,
                "city": hit.record.city,
                "industry": _industry_cell(hit.record, code),
                "naics": ", ".join(hit.record.naics),
                "project": _clip(hit.record.project, 90),
                "permits": hit.record.permit_count or "",
                "latest": _latest_text(hit.record),
                "contact_text": _contact_text(hit.record),
                "contact_name": hit.record.contact_name,
                "contact_title": hit.record.contact_title,
                "channels": _channels(hit.record),
                "score": hit.score,
                "fit": _fit_label(hit.score),
                "size": f"{count} employees" if count is not None else "Size not in public record",
                "label": hit.label,
                "stale": "Stale record" if hit.stale else "",
                "source": SOURCE_LABELS.get(hit.source, hit.source),
                "why": hit.reason or _why(hit),
                "prospect_id": hit.prospect_id,
                "url": hit.record.source_url,
            }
        )
        prospects.append(
            {"prospect_id": hit.prospect_id, "prospect": hit.prospect.model_dump(mode="json")}
        )
    counts = {
        "found": outcome.total_matches,
        "named": outcome.named_contacts,
        "held": outcome.held_back,
        "size": getattr(outcome, "size_line", "") or "",
    }
    summary = _summary(counts, len(rows))
    filt = outcome.filter
    parts = [f"sources: {', '.join(filt.sources)}"]
    for label, value in (
        ("naics", ", ".join(filt.naics)),
        ("state", filt.state),
        ("city", filt.city),
        ("business type", filt.business_type),
        ("permit type", filt.permit_type),
        ("area", filt.area),
        ("from", filt.date_from),
        ("to", filt.date_to),
    ):
        if value:
            parts.append(f"{label}: {value}")
    return {
        "summary": summary,
        "counts": counts,
        "shown": outcome.shown,
        "rows": rows,
        "prospects": prospects,
        "messages": list(outcome.messages),
        "unsupported": [f"not available in public records: {item}" for item in outcome.unsupported],
        "held_back_note": f"Held back: {outcome.held_back}. Those records are not shown.",
        "filter": "; ".join(parts),
        "filter_values": {
            "naics": ", ".join(filt.naics),
            "permit_type": filt.permit_type,
            "city": filt.city,
            "state": filt.state,
            "date_from": filt.date_from,
            "date_to": filt.date_to,
            "business_type": filt.business_type,
            "area": filt.area,
            "sources": list(filt.sources),
            "sizes": list(filt.sizes),
            "cities": list(filt.cities),
            "known_size_only": filt.known_size_only,
        },
        "unsupported_raw": list(outcome.unsupported),
        "market": getattr(outcome, "market", None),
        "markets": list(getattr(outcome, "markets", None) or []),
        "statuses": list(getattr(outcome, "statuses", None) or []),
        "size_note": live_size_note(current_mode()),
    }


def _clip(text: str, size: int) -> str:
    clean = " ".join(str(text or "").split())
    if sum(char.isalpha() for char in clean) < 3:
        return ""
    return clean if len(clean) <= size else clean[: size - 1].rstrip() + "…"


def _why(hit) -> str:
    """A short reason built from the record. Used when the written reason is not available."""
    record = hit.record
    parts = []
    if record.plumbing_tie == "strong":
        parts.append("permit matches the selected criteria")
    elif record.plumbing_tie == "some":
        parts.append("public permit record")
    if record.permit_count > 1:
        parts.append(f"{record.permit_count} permits")
    if record.contact_name.strip():
        parts.append("named contact")
    text = "; ".join(parts) or "public record in the service area"
    return f"{text[0].upper()}{text[1:]}."


def _summary(counts: dict, showing: int) -> str:
    """Plain words. The size breakdown appears only when a size was chosen and records carry one."""
    found = counts["found"]
    noun = "business" if found == 1 else "businesses"
    parts = [
        f"{found} {noun} found",
        f"{counts['named']} with a named contact",
        f"showing {showing}",
    ]
    if counts.get("held"):
        parts.append(f"{counts['held']} held back")
    text = " · ".join(parts)
    if counts.get("size"):
        text = f"{text}. {counts['size']}"
    return text


def _industry_cell(record, code: str) -> str:
    from leadgen.industry import title_for
    from leadgen.permits import PERMIT_SOURCES, permit_label

    title = title_for(code) if code else ""
    if title:
        return title
    if record.source in PERMIT_SOURCES and record.permit_type:
        return f"From permit: {permit_label(record.permit_type)}"
    return code


def _latest_text(record) -> str:
    day = record.permit_date or record.record_date
    return day.isoformat() if day else ""


def _contact_text(record) -> str:
    name = record.contact_name.strip()
    if not name:
        return "No named contact"
    title = record.contact_title.strip()
    return f"Named contact: {name}, {title}" if title else f"Named contact: {name}"


def _channels(record) -> str:
    parts = [record.phone, record.mailing_address]
    found = [part for part in parts if part and part.strip()]
    return ", ".join(found) if found else "No channel on record"


def _fit_label(score: int) -> str:
    if score >= 70:
        return "Hot"
    if score >= 40:
        return "Warm"
    return "Cold"


def profile_name(profile_id: str) -> str:
    """The name a person sees. The stored value stays the file id."""
    return load_profile(profile_id).display_name


def tier_label(tier: str) -> str:
    return {"hot": "Hot", "warm": "Warm", "cold": "Cold"}.get(tier, tier)


def exclusion_label(reason: str) -> str:
    return {
        "do_not_contact": "Do not contact",
        "no_consent": "No consent on file",
    }.get(reason, reason)


def status_badge(status: str) -> str:
    """Plain result. The stored status file keeps its code."""
    if status == "PENDING_APPROVAL":
        return "Waiting for your approval"
    if status == "BLOCKED":
        return "Blocked. A person needs to see the problem."
    if status == "REFUSED":
        return "Not sent. This person is outside the rules."
    if status == "APPROVED":
        return "Approved"
    return "Saved"


def run_steps(root: Path, run_dir: Path) -> list[str]:
    """Numbered sentences for one run. Model names stay on their own line."""
    events = [
        row
        for row in logbook(root, Path(run_dir).name)
        if row.get("event_type") == "model_call"
    ]
    lines: list[str] = []
    tailors = [row for row in events if row.get("actor") == "tailor"]
    if tailors:
        lines.append("1. Tailor the pitch: done")
        lines.append(_model_note(tailors[-1]))
    attempts = attempt_comparison(run_dir)
    if attempts:
        first = attempts[0]
        if first["passed"]:
            lines.append(f"Attempt {first['attempt']}. Check for problems: passed")
            lines.append("2. Write the email: done")
            lines.append("3. Check for problems: passed")
        else:
            problem = _problem_text(run_dir, first["attempt"])
            lines.append(f"Attempt {first['attempt']}. Problem found: {problem}")
            if len(attempts) > 1:
                nxt = attempts[1]
                lines.append(f"Trying again (Attempt {nxt['attempt']}).")
                if nxt["passed"]:
                    lines.append("2. Write the email: done")
                    lines.append("3. Check for problems: passed")
                else:
                    lines.append(
                        f"3. Check for problems: still blocked. {_problem_text(run_dir, nxt['attempt'])}"
                    )
    writers = [row for row in events if row.get("actor") == "drafter"]
    if writers:
        lines.append(_model_note(writers[-1]))
    scores = evaluation_view(run_dir)
    if scores:
        names = ("relevance", "specificity", "clarity", "tone")
        bits = [f"{name} {scores[name]} of 5" for name in names]
        passed = all(scores[name] >= scores["bar"] for name in names)
        word = "Passed" if passed else "Needs another look"
        lines.append(f"4. Quality score: {', '.join(bits)}. {word}.")
        graders = [row for row in events if row.get("actor") == "evaluator"]
        if graders:
            lines.append(_model_note(graders[-1]))
    return lines


def refresh_search(profile, previous: dict, edits: dict, root: Path) -> dict:
    """Rerun public-record search from the edited fields. Does not translate again."""
    from leadgen.search import execute
    from leadgen.sources.records import SearchFilter

    stored = previous.get("filter_values") or {}
    kind = str(edits.get("kind") or "").strip()
    if profile.search.naics:
        naics = [item.strip() for item in kind.split(",") if item.strip()]
        permit_type = stored.get("permit_type") or ""
    else:
        naics = [item.strip() for item in str(stored.get("naics") or "").split(",") if item.strip()]
        permit_type = kind
    location = str(edits.get("location") or "").strip()
    cities = list(stored.get("cities") or [])
    if location and location.casefold() in {city.casefold() for city in profile.search.cities}:
        cities = [city for city in profile.search.cities if city.casefold() == location.casefold()]
    date_from = str(edits.get("date_from") or "").strip()
    date_to = str(edits.get("date_to") or "").strip()
    if not _date_ok(date_from) or not _date_ok(date_to):
        view = dict(previous)
        view["field_error"] = "Use a date like 2026-05-24."
        return view
    chosen_sizes = edits.get("sizes")
    sizes = list(stored.get("sizes") or []) if chosen_sizes is None else list(chosen_sizes)
    filt = SearchFilter(
        sources=list(stored.get("sources") or []),
        naics=naics,
        state=stored.get("state") or "",
        city=location,
        cities=cities,
        business_type=str(edits.get("business_type") or "").strip(),
        permit_type=permit_type,
        date_from=date_from,
        date_to=date_to,
        area=location if profile.search.areas else (stored.get("area") or ""),
        sizes=sizes,
        known_size_only=bool(edits.get("known_size_only")),
    )
    outcome = execute(
        profile,
        filt,
        list(previous.get("unsupported_raw") or []),
        Path(root),
        request=str(previous.get("request") or "updated search"),
    )
    view = search_view(outcome)
    view["profile_id"] = profile.profile_id
    view["request"] = previous.get("request") or ""
    view["field_error"] = ""
    _limit_view(view, edits)
    return view


def draft_fields(run_dir: Path) -> dict:
    data = json.loads((Path(run_dir) / "draft.json").read_text(encoding="utf-8"))
    return {"hook": data.get("hook", ""), "bridge": data.get("bridge", "")}


def _model_note(event: dict) -> str:
    names = {"google": "Google", "anthropic": "Anthropic", "openai": "OpenAI"}
    provider = names.get(str(event.get("provider") or ""), str(event.get("provider") or ""))
    model = str(event.get("model") or "")
    seconds = (event.get("duration_ms") or 0) / 1000
    return f"{provider} {model} {seconds:.1f} s".strip()


def _problem_text(run_dir: Path, attempt: int) -> str:
    path = Path(run_dir) / f"verification.attempt{attempt}.json"
    if not path.is_file():
        return "The draft needs a change."
    payload = json.loads(path.read_text(encoding="utf-8"))
    messages = [item.get("message", "") for item in payload.get("report", {}).get("blocking", [])]
    messages = [item for item in messages if item]
    return " ".join(messages) or "The draft needs a change."


def _date_ok(value: str) -> bool:
    text = value.strip()
    if not text:
        return True
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return False
    year, month, day = text.split("-")
    return year.isdigit() and month.isdigit() and day.isdigit()


def _limit_view(view: dict, edits: dict) -> None:
    if not bool(edits.get("show_without_contact", True)):
        view["rows"] = [row for row in view["rows"] if row.get("label") == "Named contact"]
        kept = {row["prospect_id"] for row in view["rows"]}
        view["prospects"] = [item for item in view["prospects"] if item["prospect_id"] in kept]
    raw = str(edits.get("max_results") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        count = int(raw)
        view["rows"] = view["rows"][:count]
        view["prospects"] = view["prospects"][:count]
    elif raw:
        view["field_error"] = "Max results needs a whole number such as 10."
    if view.get("counts"):
        view["summary"] = _summary(view["counts"], len(view["rows"]))
