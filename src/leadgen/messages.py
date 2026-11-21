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
            "Allowed sizes: 1-49, 50-249, 250-499, 500-999",
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
