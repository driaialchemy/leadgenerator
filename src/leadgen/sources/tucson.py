"""City of Tucson commercial building permits. Read only."""

import json
from datetime import date, datetime, timezone

from leadgen.sources.records import PublicRecord, SourceQuery, clean_date

ENDPOINT = (
    "https://mapdata.tucsonaz.gov/arcgis/rest/services/PublicMaps/"
    "PermitsCode/MapServer/81/query"
)
OUT_FIELDS = "NUMBER,ADDRESS,CITY,STATUS,TYPE,ISSUEDATE,PROJECTNAME,DESCRIPTION,VALUE"
PAGE_SIZE = 2000


def tucson_params(query: SourceQuery, cap: int, offset: int = 0) -> list[tuple[str, str]]:
    """Fixed where-clause pieces. Typed search text never reaches this list."""
    clauses = ["1=1"]
    if query.date_from:
        clauses.append(f"ISSUEDATE >= DATE '{_quote(query.date_from)}'")
    if query.date_to:
        clauses.append(f"ISSUEDATE <= DATE '{_quote(query.date_to)}'")
    where = " AND ".join(clauses)
    return [
        ("where", where),
        ("outFields", OUT_FIELDS),
        ("returnGeometry", "false"),
        ("f", "json"),
        ("orderByFields", "ISSUEDATE DESC"),
        ("resultOffset", str(offset)),
        ("resultRecordCount", str(min(cap, PAGE_SIZE))),
    ]


def parse_tucson(body: str) -> list[PublicRecord]:
    data = json.loads(body)
    if "error" in data and "features" not in data:
        raise ValueError("Tucson permit response has an error.")
    if "features" not in data:
        raise ValueError("Tucson permit response has no features.")
    records = []
    for feature in data.get("features") or []:
        attrs = feature.get("attributes") or {}
        if isinstance(attrs, dict):
            records.append(_feature(attrs))
    return records


def matches_tucson(record: PublicRecord, query: SourceQuery) -> bool:
    if query.date_from and record.permit_date is not None:
        if record.permit_date < date.fromisoformat(query.date_from):
            return False
    if query.date_to and record.permit_date is not None:
        if record.permit_date > date.fromisoformat(query.date_to):
            return False
    wanted = {city.casefold() for city in query.cities}
    if wanted and record.city.casefold() not in wanted:
        return False
    return True


def _feature(attrs: dict) -> PublicRecord:
    issued = _issued(attrs.get("ISSUEDATE"))
    number = str(attrs.get("NUMBER") or "").strip()
    address = str(attrs.get("ADDRESS") or "").strip()
    project = str(attrs.get("PROJECTNAME") or "").strip()
    description = str(attrs.get("DESCRIPTION") or "").strip()
    return PublicRecord(
        source="tucson_permits",
        source_record_id=number or address or project,
        source_url=f"{ENDPOINT.rsplit('/', 1)[0]}/{number}" if number else ENDPOINT,
        record_date=issued,
        business_name=_name(project, address),
        mailing_address=address,
        city=str(attrs.get("CITY") or "Tucson").strip() or "Tucson",
        state="AZ",
        project=project or description,
        permit_type=str(attrs.get("TYPE") or "").strip(),
        permit_value=str(attrs.get("VALUE") or "").strip(),
        permit_date=issued,
    )


def _name(project: str, address: str) -> str:
    """The layer has no owner or tenant field. A short project name may be a business; a sentence is not."""
    if project and len(project) <= 40 and "." not in project:
        return project
    return address or project


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
