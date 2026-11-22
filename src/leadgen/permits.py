"""Turn city permit rows into businesses. Plain Python. No network and no model.

A permit row is not a business. This module decides which rows point at commercial
plumbing work, which text is a business or site name, and which rows are the same
business. The word lists and bands are in the profile YAML under search.permits.
"""

import re
from datetime import date

from leadgen.schemas import PermitRules
from leadgen.sources.records import PublicRecord

PERMIT_SOURCES = frozenset({"phoenix_permits", "tucson_permits"})
_SUFFIXES = frozenset("inc llc llp lp ltd co corp corporation company".split())
_ORDINAL = re.compile(r"^\d+(st|nd|rd|th)\b", re.IGNORECASE)
_DIRECTION = re.compile(r"\b(n|s|e|w|ne|nw|se|sw)\b", re.IGNORECASE)


def words_in(text: str, words: list[str]) -> bool:
    """True when any listed word or phrase appears whole inside the text."""
    low = text.casefold()
    for word in words:
        pattern = r"(?<![a-z0-9])" + re.escape(word.casefold()) + r"(?![a-z0-9])"
        if re.search(pattern, low):
            return True
    return False


def is_company(text: str, rules: PermitRules) -> bool:
    return words_in(text, rules.company_words)


def is_person_name(text: str, rules: PermitRules) -> bool:
    """Two or three plain words, none of them a company word. Not a guess at anyone's name."""
    clean = " ".join(text.replace(",", " ").split())
    parts = clean.split()
    if not 2 <= len(parts) <= 3:
        return False
    if is_company(clean, rules):
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z'.\-]*", part) for part in parts)


def is_address_or_intersection(text: str, rules: PermitRules) -> bool:
    clean = text.strip()
    if not clean:
        return False
    if re.match(r"^\d", clean):
        return True
    street = r"\b(" + "|".join(re.escape(word) for word in rules.street_words) + r")\b"
    has_street = bool(re.search(street, clean, re.IGNORECASE)) if rules.street_words else False
    if " & " in clean and (_ORDINAL.search(clean) or _DIRECTION.search(clean) or has_street):
        return True
    if has_street and re.search(r"\d", clean):
        return True
    return False


def is_description(text: str, rules: PermitRules) -> bool:
    clean = text.strip()
    if len(clean.split()) > 7 or "\n" in clean or ";" in clean or clean.endswith("."):
        return True
    if re.match(r"^[A-Za-z]{1,4}\d{4,}", clean):
        return True
    return words_in(clean, rules.description_words)


def valid_site_name(text: str, rules: PermitRules) -> bool:
    """A business or site name, not an address, an intersection, or a work description."""
    clean = " ".join(str(text or "").split())
    if len(re.findall(r"[A-Za-z]", clean)) < 3:
        return False
    if is_address_or_intersection(clean, rules):
        return False
    return not is_description(clean, rules)


def relevance(record: PublicRecord, rules: PermitRules) -> str:
    """strong, some, or empty when the permit does not point at commercial plumbing work.

    The work is judged from the permit type and the work description. The site name only says who
    the customer is: a hotel or a care home upgrades a plumbing-type permit but never rescues a sign or
    a fire alarm.
    """
    if not (rules.strong_words or rules.include_words or rules.exclude_words):
        return "some"  # a profile with no permit word lists keeps every permit
    kind, work = record.permit_type, record.project
    # The permit type decides first: a sprinkler or a sign permit stays out even when its
    # description mentions a tenant improvement.
    if words_in(kind, rules.exclude_words):
        return ""
    if words_in(kind, rules.strong_words):
        return "strong"
    if words_in(work, rules.strong_words):
        return "strong"
    if words_in(work, rules.exclude_words):
        return ""
    if words_in(kind + " " + work, rules.include_words):
        if words_in(kind + " " + work + " " + record.site_name, rules.customer_words):
            return "strong"
        return "some"
    return ""


def business_name(record: PublicRecord, rules: PermitRules) -> str:
    for kind in rules.business_order:
        if kind == "owner" and record.owner.strip():
            return " ".join(record.owner.split())
        if kind == "site_name" and valid_site_name(record.site_name, rules):
            return " ".join(record.site_name.split())
        if kind == "contractor" and record.contractor.strip():
            return " ".join(record.contractor.split())
    return ""


def name_key(value: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", value.casefold()).split()
    while words and words[-1] in _SUFFIXES:
        words.pop()
    return " ".join(words)


class PermitStats:
    """Counts for one source: rows read, excluded, dropped, and kept."""

    def __init__(self) -> None:
        self.total = 0
        self.excluded = 0
        self.dropped = 0
        self.kept = 0

    def line(self, label: str) -> str:
        noun = "record" if self.total == 1 else "records"
        parts = [f"{label}: {self.total} {noun}"]
        if self.excluded:
            parts.append(f"{self.excluded} left out, not commercial plumbing work")
        if self.dropped:
            parts.append(f"{self.dropped} dropped, no business name")
        return " · ".join(parts)


def refine(records: list[PublicRecord], rules: PermitRules) -> tuple[list[PublicRecord], PermitStats]:
    """Keep plumbing-relevant rows that have a business name. Count what was left out."""
    stats = PermitStats()
    stats.total = len(records)
    kept = []
    for record in records:
        record = _split_contact(record, rules)
        tie = relevance(record, rules)
        if not tie:
            stats.excluded += 1
            continue
        name = business_name(record, rules)
        if not name:
            stats.dropped += 1
            continue
        kept.append(record.model_copy(update={"business_name": name, "plumbing_tie": tie, "permit_count": 1}))
    stats.kept = len(kept)
    return kept, stats


def _split_contact(record: PublicRecord, rules: PermitRules) -> PublicRecord:
    """A permit contact is a person or a company. Only a person is a named contact."""
    raw = record.contractor.strip()
    if raw and not record.contact_name and is_person_name(raw, rules):
        return record.model_copy(update={"contact_name": raw, "contractor": ""})
    return record


def consolidate(records: list[PublicRecord]) -> list[PublicRecord]:
    """One row per business and city, with the permit count and the latest permit date."""
    groups: dict[tuple, list[PublicRecord]] = {}
    order: list[tuple] = []
    for record in records:
        key = (name_key(record.business_name), record.city.casefold())
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(record)
    merged = []
    for key in order:
        rows = groups[key]
        latest = max(rows, key=lambda row: row.permit_date or date.min)
        person = next((row.contact_name for row in rows if row.contact_name.strip()), "")
        tie = "strong" if any(row.plumbing_tie == "strong" for row in rows) else latest.plumbing_tie
        merged.append(
            latest.model_copy(
                update={
                    "permit_count": sum(row.permit_count or 1 for row in rows),
                    "contact_name": latest.contact_name or person,
                    "plumbing_tie": tie,
                    "recent_permit": any(row.recent_permit for row in rows),
                }
            )
        )
    return merged


def recency_band(permit_date: date | None, today: date, rules: PermitRules) -> str:
    if permit_date is None:
        return "none"
    days = (today - permit_date).days
    for name, limit in sorted(rules.recency_days.items(), key=lambda item: item[1]):
        if days <= limit:
            return name
    return "older"


def count_band(count: int, rules: PermitRules) -> str:
    if count >= rules.many_permits:
        return "many"
    if count >= 2:
        return "few"
    if count == 1:
        return "one"
    return "none"


def permit_label(permit_type: str) -> str:
    """A plain permit type for the Industry cell. The city's path is shortened to what reads well."""
    parts = [part.strip() for part in permit_type.split(";") if part.strip()]
    if not parts:
        return ""
    first, last = parts[0], parts[-1]
    if len(parts) == 1 or first.casefold().startswith("construction and trades"):
        return last
    if last.casefold() in {first.casefold(), "commercial", "commercial/industrial"}:
        return first
    return f"{first}: {last}"
