"""Normalized public records, labels, de-duplication, and suppression."""

import re
from datetime import date
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

SOURCE_LABELS = {
    "sam": "SAM.gov",
    "edgar": "SEC EDGAR",
    "phoenix_permits": "Phoenix permits",
    "tucson_permits": "Tucson permits",
    "census_cbp": "County Business Patterns",
}


class PublicRecord(BaseModel):
    """One row from a public-record source. Blank means the source had no value."""

    model_config = ConfigDict(extra="forbid")

    source: str
    source_record_id: str
    source_url: str
    record_date: date | None = None
    business_name: str = ""
    uei: str = ""
    domain: str = ""
    contact_name: str = ""
    contact_title: str = ""
    phone: str = ""
    mailing_address: str = ""
    city: str = ""
    state: str = ""
    naics: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=list)
    project: str = ""
    permit_value: str = ""
    permit_type: str = ""
    contractor: str = ""
    filing_date: date | None = None
    permit_date: date | None = None
    recent_filing: bool = False
    recent_permit: bool = False
    employee_count: int | None = None


class SourceQuery(BaseModel):
    """Constraints code is allowed to send. Every value is already allowlisted."""

    model_config = ConfigDict(extra="forbid")

    naics: list[str] = Field(default_factory=list)
    state: str = ""
    city: str = ""
    cities: list[str] = Field(default_factory=list)
    business_type: str = ""
    legal_name: str = ""
    permit_type: str = ""
    date_from: str = ""
    date_to: str = ""
    area: str = ""


class SearchFilter(BaseModel):
    """The translator's plan. Code drops anything outside the profile allowlists."""

    model_config = ConfigDict(extra="forbid")

    sources: list[str] = Field(default_factory=list)
    naics: list[str] = Field(default_factory=list)
    state: str = ""
    city: str = ""
    cities: list[str] = Field(default_factory=list)
    business_type: str = ""
    permit_type: str = ""
    date_from: str = ""
    date_to: str = ""
    area: str = ""
    unsupported: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    known_size_only: bool = False


class SuppressionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = ""
    domain: str = ""
    uei: str = ""


def normalize_name(value: str) -> str:
    """Case and whitespace only. Punctuation stays, so a shorter name does not match."""
    return " ".join(value.casefold().split())


def domain_of(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = (urlparse(text).hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


def main_label(record: PublicRecord) -> str:
    """The channel the record actually contains. Stale is not a label."""
    if record.contact_name.strip():
        return "Named contact"
    if record.phone.strip():
        return "Business phone on record"
    return "Mailing address only"


def is_stale(record: PublicRecord, freshness_days: int, today: date) -> bool:
    if record.record_date is None:
        return False
    return (today - record.record_date).days > freshness_days


def within_window(day: date | None, freshness_days: int, today: date) -> bool:
    if day is None or freshness_days < 1:
        return False
    age = (today - day).days
    return 0 <= age <= freshness_days


def dedupe_key(record: PublicRecord) -> tuple:
    uei = normalize_name(record.uei)
    if uei:
        return ("uei", uei)
    name = normalize_name(record.business_name)
    address = normalize_name(record.mailing_address)
    if name and address:
        return ("name", name, address)
    return ("id", record.source, record.source_record_id)


def name_address(record: PublicRecord) -> tuple[str, str] | None:
    name = normalize_name(record.business_name)
    address = normalize_name(record.mailing_address)
    if name and address:
        return (name, address)
    return None


def merge_records(base: PublicRecord, extra: PublicRecord) -> PublicRecord:
    """Fill blanks from the later source. The first source name stays."""
    data = base.model_dump()
    incoming = extra.model_dump()
    keep = {"source", "source_record_id", "source_url", "record_date"}
    for key, value in incoming.items():
        if key in keep:
            continue
        if key in {"recent_filing", "recent_permit"}:
            data[key] = bool(data[key] or value)
            continue
        if key in {"naics", "business_types"}:
            data[key] = list(dict.fromkeys([*data[key], *value]))
            continue
        if data.get(key) in ("", None, False) and value not in ("", None, False):
            data[key] = value
    return PublicRecord.model_validate(data)


def dedupe(records: list[PublicRecord]) -> list[PublicRecord]:
    """Collapse the same UEI, then the same business name and address."""
    by_uei: dict[str, PublicRecord] = {}
    order: list[tuple] = []
    loose: list[PublicRecord] = []
    for record in records:
        uei = normalize_name(record.uei)
        if uei:
            if uei in by_uei:
                by_uei[uei] = merge_records(by_uei[uei], record)
            else:
                by_uei[uei] = record
                order.append(("uei", uei))
        else:
            loose.append(record)
    used = set()
    for index, record in enumerate(loose):
        pair = name_address(record)
        if pair is None:
            continue
        for kind, ident in order:
            if kind == "uei" and name_address(by_uei[ident]) == pair:
                by_uei[ident] = merge_records(by_uei[ident], record)
                used.add(index)
                break
    grouped: list[PublicRecord] = []
    seen: dict[tuple, int] = {}
    for index, record in enumerate(loose):
        if index in used:
            continue
        key = dedupe_key(record)
        if key in seen:
            grouped[seen[key]] = merge_records(grouped[seen[key]], record)
        else:
            seen[key] = len(grouped)
            grouped.append(record)
    return [by_uei[ident] for kind, ident in order if kind == "uei"] + grouped


def is_suppressed(record: PublicRecord, entries: list[SuppressionEntry]) -> bool:
    name = normalize_name(record.business_name)
    uei = normalize_name(record.uei)
    domain = domain_of(record.domain)
    for entry in entries:
        if entry.uei and uei and normalize_name(entry.uei) == uei:
            return True
        if entry.business_name and name and normalize_name(entry.business_name) == name:
            return True
        if entry.domain and domain and domain_of(entry.domain) == domain:
            return True
    return False


def split_suppression(
    records: list[PublicRecord], entries: list[SuppressionEntry]
) -> tuple[list[PublicRecord], int]:
    kept = [record for record in records if not is_suppressed(record, entries)]
    return kept, len(records) - len(kept)


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_date(value: str) -> str:
    text = value.strip()
    if _DATE.fullmatch(text):
        return text
    return ""
