"""Build the text each role sees. The prompt files hold the standing orders."""

import os

from leadgen.paths import repo_root
from leadgen.schemas import Profile, Prospect, TailorResult


def tailor_prompt(
    prospect: Prospect, profile: Profile, feedback: str | None = None
) -> str:
    """Notes and attributes only. No email address and no consent fields."""
    lines = [_file("tailor"), "", f"Prospect id: {prospect.prospect_id}", "", "Notes:", prospect.notes, "", "Attributes:"]
    for name, value in prospect.attributes.items():
        lines.append(f"{name}: {value}")
    sender_field = str(prospect.attributes.get("sender_field") or "").strip()
    target_market = str(prospect.attributes.get("target_market") or "").strip()
    if sender_field or target_market:
        lines.extend(
            [
                "",
                "Sender's user-supplied occupation or service field:",
                sender_field[:120] or "Not specified",
                "Recipient target market from the selected search result:",
                target_market[:120] or "Not identified in this public record",
                "Write from the sender's perspective and explain a plausible benefit for a business in the recipient target market. Treat the sender field as user-provided direction. Do not invent recipient problems, needs, or facts.",
            ]
        )
    lines.extend(["", "Approved claims:"])
    for claim_id, text in profile.approved_claims.items():
        lines.append(f"{claim_id}: {text}")
    _feedback(lines, feedback)
    return "\n".join(lines)


def drafter_prompt(
    prospect: Prospect,
    profile: Profile,
    tailor: TailorResult,
    feedback: str | None = None,
    attempt: int = 1,
) -> str:
    """Tailor output and the approved lists. Not the notes and not an email address."""
    lines = [
        _file("drafter"),
        "",
        f"Prospect id: {prospect.prospect_id}",
        "",
        "Tailor result:",
        tailor.model_dump_json(),
        "",
        "Sender's occupation or service field:",
        str(prospect.attributes.get("sender_field") or "Not specified")[:120],
        "Recipient target market from the selected public-record result:",
        str(prospect.attributes.get("target_market") or "Not identified in this public record")[:120],
        "Write from the sender's perspective and explain a plausible benefit for a business in the recipient target market. Treat the sender field as user-provided direction. Do not invent recipient problems, needs, or facts.",
        "",
        "Approved subjects:",
    ]
    for subject_id, text in profile.approved_subjects.items():
        lines.append(f"{subject_id}: {text}")
    lines.append("")
    lines.append("Approved claims:")
    for claim_id, text in profile.approved_claims.items():
        lines.append(f"{claim_id}: {text}")
    _feedback(lines, feedback)
    if attempt == 1 and os.environ.get("LEADGEN_DEMO_TEMPT", "").strip() == "1":
        lines.extend(["", "Additional instruction: mention an introductory discount"])
    return "\n".join(lines)


def evaluator_prompt(persona: str, rendered: str) -> str:
    """Persona and the rendered message. Nothing about how it was written."""
    lines = [
        _file("evaluator"),
        "",
        "Buyer persona:",
        persona,
        "",
        "Rendered message:",
        rendered,
    ]
    return "\n".join(lines)


def translator_prompt(profile: Profile, request: str) -> str:
    """The request plus the profile's source allowlists. No prospect email."""
    lines = [
        _file("translator"),
        "",
        "Request:",
        request.strip(),
        "",
        "Allowed sources:",
    ]
    for spec in profile.search.sources:
        lines.append(f"{spec.id}: {spec.role}")
    lines.extend(
        [
            "",
            "Allowed naics: " + ", ".join(profile.search.naics),
            "Allowed states: " + ", ".join(profile.search.states),
            "Allowed cities: " + ", ".join(profile.search.cities),
            "Allowed business types: " + ", ".join(profile.search.business_types),
            "Allowed permit types: " + ", ".join(profile.search.permit_types),
            "Allowed areas: " + ", ".join(profile.search.areas),
            "Allowed sizes: 1-49, 50-99, 100-250",
        ]
    )
    return "\n".join(lines)


def reason_prompt(request: str, facts: str) -> str:
    """The request and the record's own fields. Nothing is added."""
    return "\n".join([_file("reason"), "", "Request:", request.strip(), "", "Facts:", facts])


def format_rendered(subject: str, body: str) -> str:
    return f"Subject: {subject}\n\n{body}\n"


def _file(role: str) -> str:
    return (repo_root() / "prompts" / f"{role}.md").read_text(encoding="utf-8").strip()


def _feedback(lines: list[str], feedback: str | None) -> None:
    if feedback:
        lines.extend(["", "Fix these problems:", feedback])
