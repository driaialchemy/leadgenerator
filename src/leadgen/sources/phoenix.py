"""City of Phoenix published permit points. Valuation is not on this layer."""

import json
from datetime import date, datetime, timezone

from leadgen.sources.records import PublicRecord, SourceQuery, clean_date

ENDPOINT = (
    "https://maps.phoenix.gov/pds/rest/services/ShapePHX/"
    "ShapePHXPermitsPoints/MapServer/0/query"
)
OUT_FIELDS = "RECORD_ID,PERMIT_NUMBER,PERMIT_TYPE,PROJECT,ADDRESS,PERMIT_ISSUE_DATE,CONTACT,OWNER_NAME"


def phoenix_params(query: SourceQuery, cap: int) -> list[tuple[str, str]]:
    """Fixed where-clause pieces. Values are allowlisted before they reach here."""
    clauses = ["1=1"]
    if query.permit_type:
        clauses.append(f"PERMIT_TYPE = '{_quote(query.permit_type)}'")
    if query.date_from:
        clauses.append(f"PERMIT_ISSUE_DATE >= DATE '{_quote(query.date_from)}'")
    if query.date_to:
        clauses.append(f"PERMIT_ISSUE_DATE <= DATE '{_quote(query.date_to)}'")
    if query.area:
        clauses.append(f"UPPER(ADDRESS) LIKE UPPER('%{_quote(query.area)}%')")
    where = " AND ".join(clauses)
    return [
        ("where", where),
        ("outFields", OUT_FIELDS),
        ("returnGeometry", "false"),
        ("f", "json"),
        ("resultRecordCount", str(cap)),
    ]


def parse_phoenix(body: str) -> list[PublicRecord]:
    data = json.loads(body)
    if "error" in data and "features" not in data:
        raise ValueError("Phoenix permit response has an error.")
    if "features" not in data:
        raise ValueError("Phoenix permit response has no features.")
    records = []
    for feature in data.get("features") or []:
        attrs = feature.get("attributes") or {}
        if isinstance(attrs, dict):
            records.append(_feature(attrs))
    return records


def matches_phoenix(record: PublicRecord, query: SourceQuery) -> bool:
    if query.permit_type and record.permit_type.casefold() != query.permit_type.casefold():
        return False
    if query.area and query.area.casefold() not in record.mailing_address.casefold():
        return False
    if query.date_from and record.permit_date is not None:
        if record.permit_date < date.fromisoformat(query.date_from):
            return False
    if query.date_to and record.permit_date is not None:
        if record.permit_date > date.fromisoformat(query.date_to):
            return False
    return True


def _feature(attrs: dict) -> PublicRecord:
    issued = _issued(attrs.get("PERMIT_ISSUE_DATE"))
    contact = str(attrs.get("CONTACT") or "").strip()
    owner = str(attrs.get("OWNER_NAME") or "").strip()
    record_id = str(attrs.get("RECORD_ID") or attrs.get("PERMIT_NUMBER") or "").strip()
    address = str(attrs.get("ADDRESS") or "").strip()
    return PublicRecord(
        source="phoenix_permits",
        source_record_id=record_id or address or owner,
        source_url=f"{ENDPOINT.rsplit('/', 1)[0]}/{record_id}" if record_id else ENDPOINT,
        record_date=issued,
        business_name=owner or contact,
        contact_name=contact,
        mailing_address=address,
        project=str(attrs.get("PROJECT") or "").strip(),
        permit_type=str(attrs.get("PERMIT_TYPE") or "").strip(),
        permit_value="",
        contractor=contact or owner,
        permit_date=issued,
    )


def _issued(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        millis = int(value)
        return datetime.fromtimestamp(millis / 1000, timezone.utc).date()
    text = str(value).strip()
    if clean_date(text[:10]):
        return date.fromisoformat(text[:10])
    return None


def _quote(value: str) -> str:
    return value.replace("'", "''")
