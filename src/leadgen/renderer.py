"""Fill tokens and lay out the email. Claim text comes from the profile."""

import re

from leadgen.schemas import DraftEmail, Profile, Prospect, RenderedEmail

_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
ALLOWED_TOKENS = ("contact_first_name", "organization", "region", "sender_name")


def token_values(prospect: Prospect, profile: Profile) -> dict[str, str]:
    """Values code is allowed to substitute. Empty organization stays empty."""
    parts = prospect.contact_name.split()
    first = parts[0] if parts else ""
    return {
        "contact_first_name": first,
        "organization": (prospect.organization or "").strip(),
        "region": prospect.region.strip(),
        "sender_name": profile.sender.name,
    }


def fill(text: str, values: dict[str, str]) -> str:
    """Replace known tokens. Leave anything else untouched for the verifier."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name in values:
            return values[name]
        return match.group(0)

    return _TOKEN.sub(replace, text)


def render(draft: DraftEmail, prospect: Prospect, profile: Profile) -> RenderedEmail:
    """Subject from the approved id. Bullets follow the draft's claim order."""
    if draft.subject_id not in profile.approved_subjects:
        raise ValueError(f"Subject id {draft.subject_id!r} is not on the approved list.")
    missing = [
        claim_id for claim_id in draft.claim_ids if claim_id not in profile.approved_claims
    ]
    if missing:
        raise ValueError(f"Claim id {missing[0]!r} is not on the approved list.")
    values = token_values(prospect, profile)
    bullets = "\n".join(
        f"- {profile.approved_claims[claim_id]}" for claim_id in draft.claim_ids
    )
    sender = profile.sender
    body = "\n".join(
        [
            f"Hi {values['contact_first_name']},",
            "",
            fill(draft.hook, values),
            "",
            fill(draft.bridge, values),
            "",
            bullets,
            "",
            fill(profile.cta, values),
            "",
            sender.name,
            sender.company,
            sender.postal_address,
            profile.opt_out_line,
        ]
    )
    return RenderedEmail(
        subject=fill(profile.approved_subjects[draft.subject_id], values),
        body=body,
    )
