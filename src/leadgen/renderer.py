"""Fill tokens and lay out the email. Claim text comes from the profile."""

import re

from leadgen.schemas import DraftEmail, Profile, Prospect, RenderedEmail

_TOKEN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
ALLOWED_TOKENS = ("contact_first_name", "organization", "region", "sender_name")


_COMPANY_WORDS = frozenset(
    "inc llc llp lp ltd co corp corporation company contractors contracting construction "
    "fire security systems services solutions group international development team "
    "pipeline concrete paving asphalt elevator protection building electric plumbing".split()
)


def _first_name(contact_name: str) -> str:
    """A permit contact is often a company. Only a person's name gives a first name."""
    parts = contact_name.replace(",", " ").replace(".", " ").split()
    if not parts or len(parts) > 3:
        return ""
    if any(part.casefold().strip("+&") in _COMPANY_WORDS for part in parts):
        return ""
    return parts[0]


def token_values(prospect: Prospect, profile: Profile) -> dict[str, str]:
    """Values code is allowed to substitute. Empty organization stays empty."""
    first = _first_name(prospect.contact_name)
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
    closing = [sender.name, sender.company, sender.postal_address]
    if sender.phone.strip():
        closing.append(sender.phone)
    closing.append(profile.opt_out_line)
    body = "\n".join(
        [
            f"Hi {values['contact_first_name'] or 'there'},",
            "",
            fill(draft.hook, values),
            "",
            fill(draft.bridge, values),
            "",
            bullets,
            "",
            fill(profile.cta, values),
            "",
            *closing,
        ]
    )
    return RenderedEmail(
        subject=fill(profile.approved_subjects[draft.subject_id], values),
        body=body,
    )
