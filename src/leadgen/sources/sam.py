"""SAM.gov Entity Management API, public sections only."""

import json
from datetime import date

from leadgen.sources.records import PublicRecord, SourceQuery, domain_of, normalize_name

ENDPOINT = "https://api.sam.gov/entity-information/v3/entities"
SECTIONS = "entityRegistration,coreData,pointsOfContact,assertions"


def sam_params(query: SourceQuery, cap: int, page: int = 0) -> list[tuple[str, str]]:
    """Fixed query keys. The API key is added at request time and is not in this list."""
    params = [
        ("includeSections", SECTIONS),
        ("page", str(page)),
        ("size", str(cap)),
    ]
    if query.legal_name:
        params.append(("legalBusinessName", query.legal_name))
        return params
    if query.naics:
        params.append(("naicsCode", "~".join(query.naics)))
    if query.state:
        params.append(("physicalAddressProvinceOrStateCode", query.state))
    if query.city and not query.cities:
        params.append(("physicalAddressCity", query.city))
    if query.business_type:
        params.append(("businessTypeDesc", query.business_type))
    return params


def parse_sam(body: str) -> list[PublicRecord]:
    data = json.loads(body)
    if "entityData" not in data:
        raise ValueError("SAM response has no entityData.")
    records = []
    for item in data.get("entityData") or []:
        if isinstance(item, dict):
            records.append(_entity(item))
    return records


def matches_sam(record: PublicRecord, query: SourceQuery) -> bool:
    if query.legal_name:
        return normalize_name(record.business_name) == normalize_name(query.legal_name)
    if query.naics and record.naics and not any(code in record.naics for code in query.naics):
        return False
    if query.state and record.state.casefold() != query.state.casefold():
        return False
    wanted = {city.casefold() for city in query.cities}
    if wanted:
        if record.city.casefold() not in wanted:
            return False
    elif query.city and record.city.casefold() != query.city.casefold():
        return False
    if query.business_type and not any(
        item.casefold() == query.business_type.casefold() for item in record.business_types
    ):
        return False
    return True


def _entity(item: dict) -> PublicRecord:
    registration = item.get("entityRegistration") or {}
    core = item.get("coreData") or {}
    physical = core.get("physicalAddress") or {}
    mailing = core.get("mailingAddress") or {}
    info = core.get("entityInformation") or {}
    naics = _naics(item, core)
    types = [
        str(row.get("businessTypeDesc") or row.get("businessTypeDescription") or "").strip()
        for row in (core.get("businessTypes") or {}).get("businessTypeList") or []
        if str(row.get("businessTypeDesc") or row.get("businessTypeDescription") or "").strip()
    ]
    pocs = item.get("pointsOfContact") or {}
    name, title, poc_address = _poc(pocs.get("governmentBusinessPOC"))
    if not name:
        name, title, poc_address = _poc(pocs.get("electronicBusinessPOC"))
    address = _lines(mailing) or poc_address or _lines(physical)
    uei = str(registration.get("ueiSAM") or "").strip()
    business = str(registration.get("legalBusinessName") or "").strip()
    city = str((mailing or physical).get("city") or "").strip()
    state = str((mailing or physical).get("stateOrProvinceCode") or "").strip()
    return PublicRecord(
        source="sam",
        source_record_id=uei or business,
        source_url=f"https://sam.gov/entity/{uei}" if uei else ENDPOINT,
        record_date=_day(registration.get("lastUpdateDate")),
        business_name=business,
        uei=uei,
        domain=domain_of(str(info.get("entityURL") or "")),
        contact_name=name,
        contact_title=title,
        phone="",
        mailing_address=address,
        city=city,
        state=state,
        naics=naics,
        business_types=types,
    )


def _naics(item: dict, core: dict) -> list[str]:
    goods = ((item.get("assertions") or {}).get("goodsAndServices") or {})
    found: list[str] = []
    primary = str(goods.get("primaryNaics") or "").strip()
    if primary:
        found.append(primary)
    lists = goods.get("naicsList") or (core.get("naics") or {}).get("listOfNaics") or []
    for row in lists:
        if not isinstance(row, dict):
            continue
        code = str(row.get("naicsCode") or "").strip()
        if code and code not in found:
            found.append(code)
    return found


def _poc(raw) -> tuple[str, str, str]:
    if not isinstance(raw, dict):
        return "", "", ""
    parts = [str(raw.get(key) or "").strip() for key in ("firstName", "middleInitial", "lastName")]
    name = " ".join(part for part in parts if part)
    title = str(raw.get("title") or "").strip()
    return name, title, _lines(raw)


def _lines(raw: dict) -> str:
    if not isinstance(raw, dict):
        return ""
    parts = [
        str(raw.get(key) or "").strip()
        for key in ("addressLine1", "addressLine2", "city", "stateOrProvinceCode", "zipCode")
    ]
    return ", ".join(part for part in parts if part)


def _day(value) -> date | None:
    text = str(value or "").strip()
    if len(text) >= 10:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None
