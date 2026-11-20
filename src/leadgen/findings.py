"""Note checks for the human. A finding is shown. It never blocks a draft."""

from leadgen.schemas import Finding, Profile, Prospect


def run_note_checks(prospect: Prospect, profile: Profile) -> list[Finding]:
    """Fire each check whose phrase is in the notes, and whose flag matches."""
    notes = prospect.notes.casefold()
    findings: list[Finding] = []
    for check in profile.note_checks:
        if not any(phrase.casefold() in notes for phrase in check.phrases):
            continue
        if check.flag_when is not None and not _flag_matches(prospect, check):
            continue
        findings.append(
            Finding(
                check_id=check.id,
                prospect_id=prospect.prospect_id,
                message=check.message,
            )
        )
    return findings


def _flag_matches(prospect: Prospect, check) -> bool:
    value = prospect.attributes.get(check.attribute or "")
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    bounds = check.flag_when
    if bounds.min is not None and value < bounds.min:
        return False
    if bounds.max is not None and value > bounds.max:
        return False
    return True
