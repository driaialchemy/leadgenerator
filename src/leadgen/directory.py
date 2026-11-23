"""Search the Arizona company directory in sample_data/az_companies. Code only, no network."""

import csv
from datetime import date
from functools import lru_cache
from pathlib import Path

from leadgen.paths import repo_root
from leadgen.schemas import Prospect

FOLDER = Path("sample_data") / "az_companies"
SOURCE_NAME = "Arizona company directory"
PAGE = 25


@lru_cache(maxsize=1)
def _load(root_text: str) -> tuple[list[dict], dict[str, list[dict]]]:
    folder = Path(root_text) / FOLDER
    contacts: dict[str, list[dict]] = {}
    with open(folder / "contacts.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            contacts.setdefault(row["company_id"], []).append(row)
    with open(folder / "companies.csv", newline="", encoding="utf-8") as handle:
        companies = list(csv.DictReader(handle))
    return companies, contacts


def available(root: Path | None = None) -> bool:
    base = Path(root) if root is not None else repo_root()
    return (base / FOLDER / "companies.csv").is_file()


def _matches_naics(code: str, chosen: list[str]) -> bool:
    if not chosen:
        return True
    return any(code.startswith(item) for item in chosen)


def _days_since(text: str, today: date) -> int | None:
    try:
        return max(0, (today - date.fromisoformat(text)).days)
    except ValueError:
        return None


def score(company: dict, contact: dict, today: date) -> int:
    """Deterministic fit score, 0-100, from the record only."""
    points = 0
    if contact.get("email") and contact.get("email_opt_in") == "Yes":
        points += 20
    if company.get("lead_status") == "New":
        points += 15
    event_days = _days_since(company.get("recent_event_date") or "", today)
    if company.get("recent_event") not in ("", "None") and event_days is not None and event_days <= 180:
        points += 20
    try:
        growth = float(company.get("revenue_growth_pct") or 0)
    except ValueError:
        growth = 0.0
    if growth >= 5:
        points += 10
    pains = [item for item in (company.get("pain_points") or "").split(";") if item.strip()]
    points += min(15, 5 * len(pains))
    try:
        reviews = int(company.get("google_review_count") or 0)
        rating = float(company.get("google_rating") or 0)
    except ValueError:
        reviews, rating = 0, 0.0
    if reviews < 25 or rating < 4.0:
        points += 10
    verified = _days_since(company.get("last_verified") or "", today)
    if verified is not None and verified <= 365:
        points += 10
    return min(points, 100)


def fit_label(value: int) -> str:
    if value >= 70:
        return "Hot"
    if value >= 40:
        return "Warm"
    return "Cold"


def _owner(contacts: list[dict]) -> dict:
    for row in contacts:
        if row.get("decision_role") == "Final say":
            return row
    return contacts[0] if contacts else {}


def _notes(company: dict, contact: dict) -> str:
    parts = [
        f"Industry: {company['naics_title']} (NAICS {company['naics_code']}).",
        f"Employees: {company['employees']}.",
        f"City: {company['city']}, AZ.",
    ]
    if company.get("recent_event") not in ("", "None"):
        parts.append(f"Recent event: {company['recent_event']} ({company.get('recent_event_date', '')}).")
    if company.get("pain_points"):
        parts.append(f"Stated challenges: {company['pain_points']}.")
    if company.get("website_platform"):
        parts.append(f"Website platform: {company['website_platform']}.")
    if company.get("google_review_count"):
        parts.append(f"Google rating {company.get('google_rating')} from {company['google_review_count']} reviews.")
    if contact.get("headline"):
        parts.append(f"Contact: {contact['headline']}.")
    return " ".join(parts)


def _prospect(profile, company: dict, contact: dict, today: date) -> dict:
    opted_in = contact.get("email_opt_in") == "Yes"
    last = _days_since(contact.get("last_contacted") or "", today)
    declared = getattr(profile, "attributes", {}) or {}
    attributes = {
        "in_service_area": "yes",
        "named_contact": "yes" if contact.get("first_name") else "no",
        "target_industry_match": "yes",
    }
    prospect = Prospect(
        prospect_id=company["company_id"],
        profile_id=profile.profile_id,
        contact_name=f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
        organization=company["company_name"],
        email=contact.get("email", "") if opted_in else "",
        region=company["city"],
        source="cold_list",
        last_engaged_days=last if last is not None else 9999,
        consent_status="opt_in" if opted_in else "none",
        do_not_contact=False,
        notes=_notes(company, contact),
        attributes={key: value for key, value in attributes.items() if key in declared},
        phone=contact.get("direct_phone") or company.get("main_phone", ""),
        mailing_address=f"{company['street_address']}, {company['city']}, AZ {company['zip']}",
        contact_title=contact.get("title", ""),
    )
    return prospect.model_dump(mode="json")


def _row(company: dict, contact: dict, value: int) -> dict:
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    channels = [label for label, field in (("Email", "email"), ("Phone", "direct_phone"), ("Mobile", "mobile_phone")) if contact.get(field)]
    why = []
    if company.get("recent_event") not in ("", "None"):
        why.append(f"{company['recent_event']} on {company.get('recent_event_date', '')}.")
    if company.get("pain_points"):
        why.append(f"Challenges: {company['pain_points']}.")
    why.append(f"{company['employees']} employees, {company['ownership_type'].lower()}.")
    return {
        "business": company["company_name"],
        "city": company["city"],
        "industry": company["naics_title"],
        "naics": company["naics_code"],
        "contact_text": f"{name}, {contact.get('title', '')}".strip(", "),
        "contact_name": name,
        "contact_title": contact.get("title", ""),
        "channels": " · ".join(channels),
        "score": value,
        "fit": fit_label(value),
        "size": f"{company['employees']} employees",
        "label": "Named contact" if name else "No named contact",
        "stale": "",
        "source": SOURCE_NAME,
        "why": " ".join(why),
        "prospect_id": company["company_id"],
        "url": company.get("website", ""),
    }


def search_directory(
    profile,
    naics: list[str],
    sizes: list[tuple[int, int]],
    cities: list[str] | None,
    exclude: set[str],
    root: Path | None = None,
    today: date | None = None,
    limit: int = PAGE,
) -> dict:
    """Matches ranked by score. Records in `exclude` and do-not-contact records never return."""
    base = Path(root) if root is not None else repo_root()
    day = today or date.today()
    companies, contacts = _load(str(base))
    wanted_cities = {city.casefold() for city in cities} if cities else None

    def candidates(codes: list[str]) -> list[dict]:
        found = []
        for company in companies:
            if not _matches_naics(company["naics_code"], codes):
                continue
            if wanted_cities is not None and company["city"].casefold() not in wanted_cities:
                continue
            if sizes:
                count = int(company["employees"])
                if not any(low <= count <= high for low, high in sizes):
                    continue
            found.append(company)
        return found

    notice = ""
    matched = candidates(naics)
    if not matched and naics:
        broader = sorted({code[:4] for code in naics})
        matched = candidates(broader)
        if matched:
            notice = "No exact industry match. Showing the closest related industry."
    held = [company for company in matched if company.get("do_not_contact") == "Yes"]
    fresh = [
        company
        for company in matched
        if company.get("do_not_contact") != "Yes" and company["company_id"] not in exclude
    ]
    scored = []
    for company in fresh:
        contact = _owner(contacts.get(company["company_id"], []))
        scored.append((score(company, contact, day), company, contact))
    scored.sort(key=lambda item: (-item[0], item[1]["company_name"]))
    page = scored[:limit]
    rows = [_row(company, contact, value) for value, company, contact in page]
    prospects = [
        {"prospect_id": company["company_id"], "prospect": _prospect(profile, company, contact, day)}
        for _value, company, contact in page
    ]
    already = len(matched) - len(held) - len(fresh)
    parts = [f"{len(fresh)} new businesses found", f"showing {len(rows)}"]
    if already:
        parts.append(f"{already} already found before")
    if held:
        parts.append(f"{len(held)} held back (do not contact)")
    return {
        "rows": rows,
        "prospects": prospects,
        "summary": " · ".join(parts),
        "remaining": max(0, len(fresh) - len(rows)),
        "search_notice": notice,
        "total_new": len(fresh),
    }
