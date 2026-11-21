"""SEC EDGAR submissions. A company is included only on an exact normalized name."""

import json
from datetime import date

from leadgen.sources.records import PublicRecord, normalize_name

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def submissions_url(cik: str) -> str:
    return f"https://data.sec.gov/submissions/CIK{cik}.json"


def company_url(cik: str) -> str:
    return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"


def ticker_rows(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [row for row in payload.values() if isinstance(row, dict)]
    raise ValueError("EDGAR ticker file is not a list of companies.")


def find_cik(payload: dict | list, business_name: str) -> str | None:
    """Exact normalized title. Zero matches and more than one match both return nothing."""
    target = normalize_name(business_name)
    if not target:
        return None
    found: list[str] = []
    for row in ticker_rows(payload):
        title = normalize_name(str(row.get("title") or ""))
        if title != target:
            continue
        cik = str(row.get("cik_str") or "").strip()
        if cik.isdigit():
            found.append(cik.zfill(10))
    if len(found) != 1:
        return None
    return found[0]


def parse_submission(body: str) -> date | None:
    data = json.loads(body)
    recent = ((data.get("filings") or {}).get("recent") or {})
    dates = recent.get("filingDate") or []
    parsed = [_day(value) for value in dates]
    days = [day for day in parsed if day is not None]
    if not days:
        return None
    return max(days)


def attach_filings(
    records: list[PublicRecord], filings: dict[str, date | None], today: date, freshness_days: int
) -> list[PublicRecord]:
    """Add a filing date to a company already on the list. A miss adds nothing."""
    updated: list[PublicRecord] = []
    for record in records:
        day = filings.get(normalize_name(record.business_name))
        if day is None and normalize_name(record.business_name) not in filings:
            updated.append(record)
            continue
        recent = False
        if day is not None:
            age = (today - day).days
            recent = 0 <= age <= freshness_days
        data = record.model_dump()
        data["filing_date"] = day
        data["recent_filing"] = recent
        updated.append(PublicRecord.model_validate(data))
    return updated


def _day(value) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
