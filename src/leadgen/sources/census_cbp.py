"""Read-only County Business Patterns counts. No business names, no headcount estimates."""

import json
import os
import urllib.parse
from pathlib import Path

from leadgen.industry import BANDS, band_for_census, title_for
from leadgen.paths import repo_root
from leadgen.sources.cache import cache_file, read_cache, write_cache
from leadgen.sources.transport import TIMEOUT_SECONDS, SourceFailure

YEAR = "2023"
ENDPOINT = f"https://api.census.gov/data/{YEAR}/cbp"
SOURCE_PAGE = "https://www.census.gov/programs-surveys/cbp/data.html"
FAILURE = (
    "County Business Patterns did not respond. The business search is unchanged."
)
NEEDS_KEY = (
    "County Business Patterns is not set up. Add CENSUS_API_KEY to your key file in "
    r"C:\Users\msell\secrets. The business search is unchanged."
)
_UNAVAILABLE = "unavailable"
_SIZE_CODES = tuple(code for band in BANDS for code in band.census)


def cbp_params(naics: str, state_fips: str, county_fips: str, empszes: str) -> list[tuple[str, str]]:
    """One fixed query. The key is not included. A non-digit value is refused."""
    code = _digits(naics, 2, 6)
    state = _digits(state_fips, 2, 2)
    county = _digits(county_fips, 3, 3)
    size = _digits(empszes, 3, 3)
    if size not in _SIZE_CODES:
        raise ValueError("size")
    return [
        ("get", "ESTAB,NAICS2017,EMPSZES"),
        ("for", f"county:{county}"),
        ("in", f"state:{state}"),
        ("NAICS2017", code),
        ("EMPSZES", size),
        ("LFO", "001"),
    ]


def cache_material(params: list[tuple[str, str]]) -> str:
    """The cache name. Callers add the API key only on the request, after this string."""
    return ENDPOINT + "|" + urllib.parse.urlencode(params)


def parse_cbp(body: str) -> list[dict]:
    """Rows of establishment counts. Size classes outside the four bands are omitted."""
    data = json.loads(body)
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("census")
    header = [str(item).casefold() for item in data[0]]
    indexes = {name: header.index(name) for name in ("estab", "naics2017", "empszes")}
    state_at = header.index("state") if "state" in header else None
    county_at = header.index("county") if "county" in header else None
    rows = []
    for raw in data[1:]:
        if not isinstance(raw, list):
            continue
        empszes = _cell(raw, indexes["empszes"])
        if not band_for_census(empszes):
            continue
        rows.append(
            {
                "naics": _cell(raw, indexes["naics2017"]),
                "empszes": empszes,
                "estab": _estab(_cell(raw, indexes["estab"])),
                "state": _cell(raw, state_at) if state_at is not None else "",
                "county": _cell(raw, county_at) if county_at is not None else "",
            }
        )
    return rows


def sum_bands(rows: list[dict], naics: str, state_fips: str, county_fips: str) -> dict[str, int]:
    totals = {band.id: 0 for band in BANDS}
    for row in rows:
        if row["naics"] != naics or row["state"] != state_fips or row["county"] != county_fips:
            continue
        band_id = band_for_census(row["empszes"])
        if band_id:
            totals[band_id] += int(row["estab"])
    return totals


def load_market(
    county,
    naics_codes: list[str],
    band_ids: list[str],
    root: Path,
    hours: int,
    network: bool,
    transport,
) -> tuple[dict | None, str]:
    """County establishment totals, or a plain failure. This never raises."""
    codes = [code for code in naics_codes if code.isdigit()]
    if not codes:
        return None, ""
    try:
        state_fips = _digits(str(county.state_fips), 2, 2)
        county_fips = _digits(str(county.county_fips), 3, 3)
        if network:
            rows = _live_rows(codes, band_ids, state_fips, county_fips, root, hours, transport)
        else:
            rows = parse_cbp(_fixture())
    except (SourceFailure, ValueError, OSError, json.JSONDecodeError, TimeoutError, KeyError, TypeError):
        if network and not os.environ.get("CENSUS_API_KEY", "").strip():
            return None, NEEDS_KEY
        return None, FAILURE
    selected = [band for band in BANDS if not band_ids or band.id in band_ids]
    industries = []
    for code in codes:
        totals = sum_bands(rows, code, state_fips, county_fips)
        industries.append(
            {
                "code": code,
                "title": title_for(code) or code,
                "bands": [
                    {"id": band.id, "label": band.label, "count": totals[band.id]}
                    for band in selected
                ],
            }
        )
    place = _place(county)
    return {
        "year": YEAR,
        "county": place,
        "note": f"County totals for {place}. This is not a list of businesses.",
        "url": SOURCE_PAGE,
        "industries": industries,
    }, ""


def _live_rows(codes, band_ids, state_fips, county_fips, root, hours, transport) -> list[dict]:
    wanted = [
        size
        for band in BANDS
        if not band_ids or band.id in band_ids
        for size in band.census
    ]
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    rows = []
    for code in codes:
        for size in wanted:
            params = cbp_params(code, state_fips, county_fips, size)
            body = _cached_body(params, root, hours, transport, key)
            rows.extend(parse_cbp(body))
    return rows


def _cached_body(params, root, hours, transport, key: str) -> str:
    material = cache_material(params)
    path = cache_file(root, "census_cbp", material)
    cached = read_cache(path, hours)
    if cached is not None:
        if cached == _UNAVAILABLE:
            raise SourceFailure("census_cbp", "down")
        return cached
    wire = list(params)
    if key:
        wire.append(("key", key))
    try:
        status, body = transport(ENDPOINT, wire, {"Accept": "application/json"}, TIMEOUT_SECONDS)
    except TimeoutError:
        raise SourceFailure("census_cbp", "timeout") from None
    except OSError:
        raise SourceFailure("census_cbp", "down") from None
    if status != 200:
        write_cache(path, _UNAVAILABLE)
        raise SourceFailure("census_cbp", "down")
    try:
        parse_cbp(body)
    except (ValueError, json.JSONDecodeError):
        write_cache(path, _UNAVAILABLE)
        raise SourceFailure("census_cbp", "down") from None
    write_cache(path, body)
    return body


def _fixture() -> str:
    path = repo_root() / "sample_data" / "source_fixtures" / "census" / "cbp.json"
    return path.read_text(encoding="utf-8")


def _place(county) -> str:
    name = str(county.name or "").strip() or "Maricopa"
    if not name.casefold().endswith("county"):
        name = f"{name} County"
    state = str(county.state or "").strip()
    return f"{name}, {state}" if state else name


def _digits(value: str, low: int, high: int) -> str:
    text = str(value).strip()
    if not text.isdigit() or not low <= len(text) <= high:
        raise ValueError("digits")
    return text


def _cell(row: list, index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _estab(value: str) -> int:
    if value.isdigit():
        return int(value)
    return 0
