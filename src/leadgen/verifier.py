"""Blocking checks on AI-written text. Findings are reported and do not block."""

import re

from leadgen.exclusions import apply_exclusions
from leadgen.findings import run_note_checks
from leadgen.phrases import is_banned
from leadgen.renderer import token_values
from leadgen.schemas import (
    BlockingIssue,
    DraftEmail,
    PipelineConfig,
    Profile,
    Prospect,
    TailorResult,
    VerifyReport,
)
from leadgen.scoring import score

_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")
_ALLOWED_TOKENS = {"contact_first_name", "organization", "region", "sender_name"}


class IneligibleProspect(RuntimeError):
    """The prospect is excluded or below the draft threshold."""


def verify(
    tailor: TailorResult,
    draft: DraftEmail,
    prospect: Prospect,
    profile: Profile,
    pipeline: PipelineConfig,
) -> VerifyReport:
    """Recompute eligibility, then inspect the AI-written fields."""
    _require_eligible(prospect, profile, pipeline)
    blocking: list[BlockingIssue] = []
    blocking += _empty_text(draft)
    blocking += _tokens(draft, prospect, profile)
    blocking += _raw_facts(draft, prospect)
    blocking += _digits(draft, profile)
    blocking += _banned(draft, profile)
    blocking += _too_long(draft, pipeline)
    blocking += _subject(draft, profile)
    blocking += _unknown_claims(tailor, draft, profile)
    blocking += _claim_count(tailor, draft, pipeline)
    blocking += _claim_mismatch(tailor, draft)
    blocking += _missing_evidence(tailor, draft)
    blocking += _evidence_quotes(tailor, prospect)
    return VerifyReport(
        passed=not blocking,
        blocking=blocking,
        findings=run_note_checks(prospect, profile),
    )


def _require_eligible(
    prospect: Prospect, profile: Profile, pipeline: PipelineConfig
) -> None:
    _eligible, excluded = apply_exclusions([prospect], pipeline)
    if excluded:
        raise IneligibleProspect(
            f"{prospect.prospect_id} is excluded ({excluded[0].reason}). "
            "The verifier will not check a draft."
        )
    result = score(prospect, profile, pipeline)
    if not result.draft_eligible:
        raise IneligibleProspect(
            f"{prospect.prospect_id} scored {result.total}, below the draft threshold "
            f"of {pipeline.draft_threshold}. The verifier will not check a draft."
        )


def _empty_text(draft: DraftEmail) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    for field in ("hook", "bridge"):
        if not getattr(draft, field).strip():
            issues.append(
                BlockingIssue(
                    code="empty_text",
                    field=field,
                    message=f"Write a {field}. It is blank.",
                )
            )
    return issues


def _tokens(
    draft: DraftEmail, prospect: Prospect, profile: Profile
) -> list[BlockingIssue]:
    values = token_values(prospect, profile)
    issues: list[BlockingIssue] = []
    for field in ("hook", "bridge"):
        for match in _TOKEN.finditer(getattr(draft, field)):
            name = match.group(1).strip()
            token = "{{" + name + "}}"
            if name not in _ALLOWED_TOKENS:
                issues.append(
                    BlockingIssue(
                        code="unknown_token",
                        field=field,
                        message=(
                            f"Remove {token} from {field}. Allowed tokens are "
                            "contact_first_name, organization, region, and sender_name."
                        ),
                    )
                )
            elif not values.get(name, "").strip():
                issues.append(
                    BlockingIssue(
                        code="empty_token",
                        field=field,
                        message=(
                            f"Remove {token} from {field}. "
                            "That value is empty for this prospect."
                        ),
                    )
                )
    return issues


def _raw_facts(draft: DraftEmail, prospect: Prospect) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    for fact in _fact_list(prospect):
        for field in ("hook", "bridge"):
            if _fact_in_text(getattr(draft, field), fact):
                issues.append(
                    BlockingIssue(
                        code="raw_fact",
                        field=field,
                        message=(
                            f"Remove '{fact}' from {field}. "
                            "Use a token instead of typing the prospect's details."
                        ),
                    )
                )
    return issues


def _fact_list(prospect: Prospect) -> list[str]:
    parts = prospect.contact_name.split()
    facts: list[str] = []
    if parts:
        facts.append(parts[0])
        if len(parts) > 1 and parts[-1].casefold() != parts[0].casefold():
            facts.append(parts[-1])
    if prospect.organization and prospect.organization.strip():
        facts.append(prospect.organization.strip())
    if prospect.region and prospect.region.strip():
        facts.append(prospect.region.strip())
    if prospect.email and prospect.email.strip():
        facts.append(prospect.email.strip())
    return facts


def _fact_in_text(text: str, fact: str) -> bool:
    if any(not (character.isalpha() or character.isspace()) for character in fact):
        return fact.casefold() in text.casefold()
    pattern = r"\b" + re.escape(fact.casefold()) + r"\b"
    return re.search(pattern, text.casefold()) is not None


def _digits(draft: DraftEmail, profile: Profile) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    for field in ("hook", "bridge"):
        text = _without_claims(getattr(draft, field), profile)
        for match in _NUMBER.finditer(text):
            number = match.group(0)
            issues.append(
                BlockingIssue(
                    code="digits",
                    field=field,
                    message=(
                        f"Remove the number '{number}' from {field}; "
                        "figures are not allowed in AI-written text."
                    ),
                )
            )
    return issues


def _without_claims(text: str, profile: Profile) -> str:
    cleaned = text
    for claim in profile.approved_claims.values():
        if claim:
            cleaned = cleaned.replace(claim, " ")
    return cleaned


def _banned(draft: DraftEmail, profile: Profile) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    for field in ("hook", "bridge"):
        text = getattr(draft, field)
        for phrase in profile.banned_phrases:
            if is_banned(text, phrase):
                issues.append(
                    BlockingIssue(
                        code="banned_phrase",
                        field=field,
                        message=f"Remove the banned phrase '{phrase}' from {field}.",
                    )
                )
    return issues


def _too_long(draft: DraftEmail, pipeline: PipelineConfig) -> list[BlockingIssue]:
    count = len(draft.hook.split()) + len(draft.bridge.split())
    if count <= pipeline.max_ai_words:
        return []
    return [
        BlockingIssue(
            code="too_long",
            field="hook",
            message=(
                f"Shorten hook and bridge to {pipeline.max_ai_words} words or fewer. "
                f"They are {count} words."
            ),
        )
    ]


def _subject(draft: DraftEmail, profile: Profile) -> list[BlockingIssue]:
    if draft.subject_id in profile.approved_subjects:
        return []
    return [
        BlockingIssue(
            code="unknown_subject",
            field="subject_id",
            message=(
                f"Subject id '{draft.subject_id}' is not on the approved list. "
                "Pick an approved subject id."
            ),
        )
    ]


def _unknown_claims(
    tailor: TailorResult, draft: DraftEmail, profile: Profile
) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    reported: set[str] = set()
    for claim_id in [*tailor.claim_ids, *draft.claim_ids]:
        if claim_id in profile.approved_claims or claim_id in reported:
            continue
        reported.add(claim_id)
        issues.append(
            BlockingIssue(
                code="unknown_claim",
                field="claim_ids",
                message=(
                    f"Claim id '{claim_id}' is not on the approved list. "
                    "Pick an approved claim id."
                ),
            )
        )
    return issues


def _claim_count(
    tailor: TailorResult, draft: DraftEmail, pipeline: PipelineConfig
) -> list[BlockingIssue]:
    issues: list[BlockingIssue] = []
    for label, claim_ids in (("tailor", tailor.claim_ids), ("draft", draft.claim_ids)):
        count = len(claim_ids)
        if count < 1 or count > pipeline.max_claims:
            issues.append(
                BlockingIssue(
                    code="claim_count",
                    field="claim_ids",
                    message=(
                        f"Use 1 to {pipeline.max_claims} approved claims. "
                        f"This {label} has {count}."
                    ),
                )
            )
        repeated = []
        for claim_id in claim_ids:
            if claim_ids.count(claim_id) > 1 and claim_id not in repeated:
                repeated.append(claim_id)
        if repeated:
            names = ", ".join(f"'{claim_id}'" for claim_id in repeated)
            issues.append(
                BlockingIssue(
                    code="claim_count",
                    field="claim_ids",
                    message=f"Use each approved claim once. This {label} repeats {names}.",
                )
            )
    return issues


def _claim_mismatch(tailor: TailorResult, draft: DraftEmail) -> list[BlockingIssue]:
    if set(tailor.claim_ids) == set(draft.claim_ids):
        return []
    return [
        BlockingIssue(
            code="claim_mismatch",
            field="claim_ids",
            message=(
                "Make the draft claim ids match the tailor claim ids. "
                f"Tailor has {list(tailor.claim_ids)}. Draft has {list(draft.claim_ids)}."
            ),
        )
    ]


def _missing_evidence(tailor: TailorResult, draft: DraftEmail) -> list[BlockingIssue]:
    quoted = {
        item.claim_id
        for item in tailor.evidence
        if item.quote.strip()
    }
    issues: list[BlockingIssue] = []
    seen: set[str] = set()
    for claim_id in draft.claim_ids:
        if claim_id in seen:
            continue
        seen.add(claim_id)
        if claim_id not in quoted:
            issues.append(
                BlockingIssue(
                    code="missing_evidence",
                    field="evidence",
                    message=(
                        f"Add a notes quote for claim '{claim_id}'. "
                        "Every claim needs evidence from the notes."
                    ),
                )
            )
    return issues


def _evidence_quotes(tailor: TailorResult, prospect: Prospect) -> list[BlockingIssue]:
    notes = _collapse(prospect.notes)
    issues: list[BlockingIssue] = []
    for item in tailor.evidence:
        collapsed = _collapse(item.quote)
        if len(item.quote.split()) < 2 or collapsed not in notes:
            issues.append(
                BlockingIssue(
                    code="evidence_not_in_notes",
                    field="evidence",
                    message=(
                        f"Quote '{item.quote}' is not in the notes, or it is shorter "
                        "than two words. Quote a real phrase from the notes."
                    ),
                )
            )
    return issues


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()
