"""City of Phoenix published permit points. Valuation is not on this layer."""

import json
from datetime import date, datetime, timezone

from leadgen.permits import keyword_clause
from leadgen.sources.records import PublicRecord, SourceQuery, clean_date

ENDPOINT = (
    "https://maps.phoenix.gov/pds/rest/services/ShapePHX/"
    "ShapePHXPermitsPoints_DL/MapServer/0/query"
)
OUT_FIELDS = (
    "RECORD_ID,PERMIT_NUMBER,PERMIT_TYPE,PERMIT_NAME,SCOPE,PROJECT,ADDRESS,"
    "PERMIT_ISSUE_DATE,CONTACT,OWNER_NAME"
)
# The city's permit types are semicolon paths such as
# "Construction and Trades Commercial;Commercial;Commercial/Industrial;Electrical Work".
# "Building" in the profile means any commercial permit.
COMMERCIAL = ";Commercial;"
COMMERCIAL_CLAUSE = "PERMIT_TYPE LIKE '%;Commercial;%'"


def phoenix_params(query: SourceQuery, cap: int, offset: int = 0) -> list[tuple[str, str]]:
    """Fixed where-clause pieces. Values are allowlisted before they reach here."""
    clauses = ["1=1"]
    if query.permit_type:
        if query.permit_type.casefold() == "building":
            clauses.append(COMMERCIAL_CLAUSE)
        else:
            clauses.append(f"PERMIT_TYPE = '{_quote(query.permit_type)}'")
    if query.date_from:
        clauses.append(f"PERMIT_ISSUE_DATE >= DATE '{_quote(query.date_from)}'")
    if query.date_to:
        clauses.append(f"PERMIT_ISSUE_DATE <= DATE '{_quote(query.date_to)}'")
    if query.area:
        clauses.append(f"UPPER(ADDRESS) LIKE UPPER('%{_quote(query.area)}%')")
    named = keyword_clause(["PERMIT_NAME", "SCOPE", "OWNER_NAME"], query.keywords)
    if named:
        clauses.append(named)
    where = " AND ".join(clauses)
    return [
        ("where", where),
        ("outFields", OUT_FIELDS),
        ("returnGeometry", "false"),
        ("f", "json"),
        ("orderByFields", "PERMIT_ISSUE_DATE DESC"),
        ("resultOffset", str(offset)),
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
    if query.permit_type and not _type_ok(record.permit_type, query.permit_type):
        return False
    if query.area and query.area.casefold() not in record.mailing_address.casefold():
        return False
    wanted = {city.casefold() for city in query.cities}
    if wanted and record.city.casefold() not in wanted:
        return False
    if query.date_from and record.permit_date is not None:
        if record.permit_date < date.fromisoformat(query.date_from):
            return False
    if query.date_to and record.permit_date is not None:
        if record.permit_date > date.fromisoformat(query.date_to):
            return False
    return True


def _type_ok(actual: str, wanted: str) -> bool:
    if actual.casefold() == wanted.casefold():
        return True
    return wanted.casefold() == "building" and COMMERCIAL in actual


def _feature(attrs: dict) -> PublicRecord:
    """Raw fields only. Which one is the business is decided later, from the profile rules."""
    issued = _issued(attrs.get("PERMIT_ISSUE_DATE"))
    record_id = str(attrs.get("RECORD_ID") or attrs.get("PERMIT_NUMBER") or "").strip()
    address = str(attrs.get("ADDRESS") or "").strip()
    owner = str(attrs.get("OWNER_NAME") or "").strip()
    contact = str(attrs.get("CONTACT") or "").strip()
    site = str(attrs.get("PERMIT_NAME") or "").strip()
    scope = str(attrs.get("SCOPE") or attrs.get("PROJECT") or "").strip()
    return PublicRecord(
        source="phoenix_permits",
        source_record_id=record_id or address or owner or site,
        source_url=f"{ENDPOINT.rsplit('/', 1)[0]}/{record_id}" if record_id else ENDPOINT,
        record_date=issued,
        owner=owner,
        site_name=site,
        contractor=contact,
        mailing_address=address,
        city="Phoenix",
        state="AZ",
        project=_first_line(scope or site),
        permit_type=str(attrs.get("PERMIT_TYPE") or "").strip(),
        permit_value="",
        permit_date=issued,
    )


def _first_line(text: str) -> str:
    line = " ".join(text.splitlines()[0].split()) if text.strip() else ""
    return line[:160]


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
