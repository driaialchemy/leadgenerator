"""Turn a plain-language request into a ranked public-record shortlist."""

import hashlib
import json
import time
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from leadgen.industry import codes_for_request, keep_record, size_line, terms_for
from leadgen.json_text import parse_model_json
from leadgen.kill_switch import assert_not_engaged
from leadgen.llm import ProviderError, complete, scrub
from leadgen.messages import reason_prompt, translator_prompt
from leadgen.paths import repo_root
from leadgen.pipeline import _log
from leadgen.profiles import load_pipeline_config
from leadgen.schemas import CountyConfig, PipelineConfig, Profile, Prospect
from leadgen.scoring import score
from leadgen.sources.cache import cache_file, read_cache, write_cache
from leadgen.sources.census_cbp import ENDPOINT as CENSUS_ENDPOINT
from leadgen.sources.census_cbp import load_market
from leadgen.sources.edgar import (
    TICKERS_URL,
    attach_filings,
    find_cik,
    parse_submission,
    submissions_url,
)
from leadgen.permits import (
    PERMIT_SOURCES,
    consolidate,
    matches_business,
    refine,
)
from leadgen.sources.phoenix import ENDPOINT as PHOENIX_ENDPOINT
from leadgen.sources.phoenix import matches_phoenix, parse_phoenix, phoenix_params
from leadgen.sources.records import (
    SOURCE_LABELS,
    PublicRecord,
    SearchFilter,
    SourceQuery,
    SuppressionEntry,
    clean_date,
    dedupe,
    is_stale,
    main_label,
    normalize_name,
    split_suppression,
    within_window,
)
from leadgen.sources.sam import ENDPOINT as SAM_ENDPOINT
from leadgen.sources.sam import matches_sam, parse_sam, sam_params
from leadgen.sources.transport import TIMEOUT_SECONDS, SourceFailure, fetch
from leadgen.sources.tucson import ENDPOINT as TUCSON_ENDPOINT
from leadgen.sources.tucson import PAGE_SIZE as TUCSON_PAGE
from leadgen.sources.tucson import matches_tucson, parse_tucson, tucson_params
from leadgen.reasons import reason_is_grounded


class SearchHit:
    def __init__(self, record, label, stale, fit, scored, reason, prospect):
        self.record = record
        self.label = label
        self.stale = stale
        self.fit = fit
        self.score = scored
        self.reason = reason
        self.prospect = prospect
        self.prospect_id = prospect.prospect_id
        self.business_name = record.business_name
        self.source = record.source


class SearchOutcome:
    def __init__(
        self,
        hits,
        total_matches,
        named_contacts,
        shown,
        held_back,
        messages,
        unsupported,
        filt,
        market=None,
        size_line="",
        statuses=None,
        markets=None,
    ):
        self.hits = hits
        self.total_matches = total_matches
        self.named_contacts = named_contacts
        self.shown = shown
        self.held_back = held_back
        self.messages = messages
        self.unsupported = unsupported
        self.filter = filt
        self.market = market
        self.size_line = size_line
        self.statuses = list(statuses or [])
        self.markets = list(markets or [])


def search(
    profile: Profile,
    request: str,
    root: Path | None = None,
    pipeline: PipelineConfig | None = None,
    today: date | None = None,
    network: bool | None = None,
    transport=None,
    lookup_cap: int | None = None,
    chosen_naics: list[str] | None = None,
    chosen_sizes: list[str] | None = None,
    known_size_only: bool = False,
    chosen_cities: list[str] | None = None,
    fresh: bool = False,
) -> SearchOutcome:
    """Rank public records. On-screen fields run the search. Free text may add a filter."""
    folder = Path(root) if root is not None else repo_root()
    assert_not_engaged(folder)
    _log(folder, "search", "search", "search", "ok", scrub(request)[:240] or "search")
    filt = screen_filter(profile, chosen_naics, chosen_sizes, chosen_cities, known_size_only)
    unsupported: list[str] = []
    notes: list[str] = []
    if request.strip():
        try:
            translated, unsupported = translate(profile, request, folder)
        except (ValueError, json.JSONDecodeError, ValidationError, ProviderError, FileNotFoundError, OSError):
            notes.append("The request could not be read. The search used the fields on screen.")
            if not filt.naics:
                codes = codes_for_request(request)
                if codes:
                    filt = filt.model_copy(update={"naics": codes})
        else:
            updates = {}
            if not filt.naics and translated.naics:
                updates["naics"] = translated.naics
            if not filt.sizes and translated.sizes:
                updates["sizes"] = translated.sizes
            if updates:
                filt = filt.model_copy(update=updates)
    return execute(
        profile,
        filt,
        unsupported,
        folder,
        pipeline=pipeline,
        today=today,
        network=network,
        transport=transport,
        lookup_cap=lookup_cap,
        request=request,
        notes=notes,
        fresh=fresh,
    )


def execute(
    profile: Profile,
    filt: SearchFilter,
    unsupported: list[str],
    root: Path,
    pipeline: PipelineConfig | None = None,
    today: date | None = None,
    network: bool | None = None,
    transport=None,
    lookup_cap: int | None = None,
    request: str = "",
    notes: list[str] | None = None,
    fresh: bool = False,
) -> SearchOutcome:
    config = pipeline or load_pipeline_config()
    day = today or date.today()
    use_network = _network(network)
    caller = transport or fetch
    cap = config.source_record_cap
    hours = config.source_cache_hours
    windows = {spec.id: spec.freshness_days for spec in profile.search.sources}
    specs = {spec.id: spec for spec in profile.search.sources}
    messages: list[str] = list(notes or [])
    records: list[PublicRecord] = []
    source_counts: dict[str, int] = {}
    statuses: list[str] = []
    terms = terms_for(filt.naics)
    query = _query(filt)
    if terms:
        query = query.model_copy(update={"keywords": terms})
    sam_stopped = False
    for source_id in filt.sources:
        spec = specs.get(source_id)
        if spec is None or spec.role != "search":
            continue
        found, failure = _search_source(
            source_id,
            query,
            root,
            cap,
            hours,
            use_network,
            caller,
            day,
            config.sam_page_budget,
            fresh,
        )
        label = SOURCE_LABELS.get(source_id, source_id)
        permit_stats = None
        aside = 0
        if source_id in PERMIT_SOURCES:
            found, permit_stats = refine(found, profile.search.permits)
            permit_stats.total = permit_stats.total or 0
            if terms:
                matched = [row for row in found if matches_business(row, terms)]
                aside = len(found) - len(matched)
                found = matched
        source_counts[source_id] = len(found)
        records.extend(found)
        if failure:
            if source_id == "sam":
                sam_stopped = True
            statuses.append(failure if failure == SAM_DAILY or failure.startswith(label) else f"{label}: {failure}")
        elif permit_stats is not None:
            line = permit_stats.line(label)
            if aside:
                line += f" · {aside} left out, not the kind of business you asked for"
            statuses.append(line)
        else:
            noun = "record" if len(found) == 1 else "records"
            statuses.append(f"{label}: {len(found)} {noun}")
    if not sam_stopped and any(spec.role == "lookup" and spec.id in filt.sources for spec in profile.search.sources):
        names = []
        for record in records:
            if record.business_name and record.business_name not in names:
                names.append(record.business_name)
        limit = cap if lookup_cap is None else lookup_cap
        for name in names[:limit]:
            found, failure = _search_source(
                "sam",
                SourceQuery(legal_name=name),
                root,
                cap,
                hours,
                use_network,
                caller,
                day,
            )
            if failure is not None:
                if failure not in messages and not any(failure in line for line in statuses):
                    messages.append(failure)
                break
            records.extend(found)
    permit_rows = [record for record in records if record.source in PERMIT_SOURCES]
    if permit_rows:
        records = [record for record in records if record.source not in PERMIT_SOURCES] + consolidate(
            permit_rows
        )
    merged = dedupe(records)
    markets, market_message = _markets(
        profile, filt, root, hours, use_network, caller
    )
    market = markets[0] if markets else None
    if market_message:
        messages.append(market_message)
    if filt.naics:
        census_count = 0
        if market:
            census_count = sum(
                band["count"] for industry in market["industries"] for band in industry["bands"]
            )
        source_counts["census_cbp"] = census_count
        _source_log(
            root,
            "census_cbp",
            CENSUS_ENDPOINT,
            "fail" if market_message else "ok",
            census_count,
            0,
            False,
        )
    if "edgar" in filt.sources:
        merged, failure = _enrich_edgar(
            merged, root, hours, use_network, caller, day, windows.get("edgar", 0)
        )
        if failure is not None:
            messages.append(failure)
    marked = [_mark(record, windows, day) for record in merged]
    kept, held_back = split_suppression(marked, load_suppression())
    sized = [record for record in kept if keep_record(record, filt.sizes, filt.known_size_only)]
    hits = _rank(profile, config, sized, filt, day)
    _fill_reasons(hits, request, profile, root)
    named = sum(1 for hit in hits if hit.label == "Named contact")
    _log(
        root,
        "search",
        "search",
        "search",
        "ok",
        scrub(
            "typed {typed} naics {naics} sizes {sizes} sources {sources}".format(
                typed=(request or "search")[:80],
                naics=",".join(filt.naics) or "none",
                sizes=",".join(filt.sizes) or "any",
                sources=" ".join(f"{key}={value}" for key, value in source_counts.items()) or "none",
            )
        )[:240],
    )
    return SearchOutcome(
        hits=hits,
        total_matches=len(marked),
        named_contacts=named,
        shown=len(hits),
        held_back=held_back,
        messages=messages,
        unsupported=unsupported,
        filt=filt,
        market=market,
        size_line=size_line(sized, filt.sizes),
        statuses=statuses,
        markets=markets,
    )


def translate(profile: Profile, request: str, root: Path) -> tuple[SearchFilter, list[str]]:
    prompt = translator_prompt(profile, request)
    text = _model(root, profile, "translator", prompt, 1, None)
    try:
        return restrict(parse_filter(text), profile)
    except (ValueError, json.JSONDecodeError, ValidationError):
        reason = "The filter was not valid."
        text = _model(root, profile, "translator", prompt, 2, reason)
        return restrict(parse_filter(text), profile)


def parse_filter(text: str) -> SearchFilter:
    return parse_model_json(text, SearchFilter)


def screen_filter(
    profile: Profile,
    naics: list[str] | None,
    sizes: list[str] | None,
    cities: list[str] | None,
    known_size_only: bool,
) -> SearchFilter:
    """The on-screen fields. Sources always come from the settings file."""
    from leadgen.industry import BAND_IDS, catalog_codes

    catalog = catalog_codes()
    codes = []
    for code in naics or []:
        if code in catalog and code not in codes:
            codes.append(code)
    bands = []
    for band in sizes or []:
        if band in BAND_IDS and band not in bands:
            bands.append(band)
    allowed = {city.casefold(): city for city in profile.search.cities}
    chosen = []
    for city in cities if cities is not None else profile.search.cities:
        match = allowed.get(str(city).casefold())
        if match and match not in chosen:
            chosen.append(match)
    if not chosen:
        chosen = list(profile.search.cities)
    return SearchFilter(
        sources=[spec.id for spec in profile.search.sources],
        naics=codes,
        state=profile.search.states[0] if profile.search.states else "",
        cities=chosen,
        sizes=bands,
        known_size_only=known_size_only,
        permit_type=profile.search.permit_types[0] if profile.search.permit_types else "",
    )


SAM_DAILY = "SAM.gov daily limit reached; results resume tomorrow"
SAM_PAGE_SIZE = 10
PHOENIX_PAGE = 1000


def restrict(filt: SearchFilter, profile: Profile) -> tuple[SearchFilter, list[str]]:
    """Drop values the profile does not list. Those asks are not queried."""
    unsupported = [item.strip() for item in filt.unsupported if item.strip()]
    allowed_sources = [spec.id for spec in profile.search.sources]
    sources = []
    for source in filt.sources:
        if source in allowed_sources and source not in sources:
            sources.append(source)
        elif source not in allowed_sources:
            unsupported.append(source)
    from leadgen.industry import BAND_IDS, catalog_codes

    naics = _keep_many(filt.naics, catalog_codes(), unsupported)
    sizes = _keep_many(filt.sizes, list(BAND_IDS), unsupported)
    state = _keep_one(filt.state, profile.search.states, unsupported)
    city = _keep_one(filt.city, profile.search.cities, unsupported)
    business_type = _keep_one(filt.business_type, profile.search.business_types, unsupported)
    permit_type = _keep_one(filt.permit_type, profile.search.permit_types, unsupported)
    area = _keep_one(filt.area, profile.search.areas, unsupported)
    date_from = clean_date(filt.date_from)
    date_to = clean_date(filt.date_to)
    if filt.date_from.strip() and not date_from:
        unsupported.append(filt.date_from.strip())
    if filt.date_to.strip() and not date_to:
        unsupported.append(filt.date_to.strip())
    cleaned = SearchFilter(
        sources=sources,
        naics=naics,
        state=state,
        city=city,
        business_type=business_type,
        permit_type=permit_type,
        date_from=date_from,
        date_to=date_to,
        area=area,
        sizes=sizes,
        known_size_only=filt.known_size_only,
    )
    return cleaned, unsupported


def load_suppression(path: Path | None = None) -> list[SuppressionEntry]:
    file = path or (repo_root() / "sample_data" / "suppression.csv")
    if not file.is_file():
        return []
    import csv

    entries = []
    with file.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entries.append(
                SuppressionEntry(
                    business_name=(row.get("business_name") or "").strip(),
                    domain=(row.get("domain") or "").strip(),
                    uei=(row.get("uei") or "").strip(),
                )
            )
    return entries


def remember_add(root: Path, prospect: Prospect) -> None:
    _log(
        root,
        prospect.prospect_id,
        "add_to_pipeline",
        "human",
        "ok",
        f"{prospect.prospect_id} {prospect.source}",
    )


def _search_source(source_id, query, root, cap, hours, network, transport, today, sam_budget=5, fresh=False):
    if source_id == "sam":
        if not query.legal_name and not (
            query.naics or query.state or query.city or query.cities or query.business_type
        ):
            return [], "SAM.gov needs a NAICS code, state, city, or business type."
        if query.legal_name:
            return _sam_once(query, root, cap, hours, network, transport, fresh)
        return _sam_pages(query, root, cap, hours, network, transport, sam_budget, fresh)
    if source_id == "phoenix_permits":
        if not (query.permit_type or query.area or query.date_from or query.date_to):
            return [], "Phoenix permits needs a permit type, date range, or area."
        return _arc_pages(
            "phoenix_permits",
            PHOENIX_ENDPOINT,
            phoenix_params,
            parse_phoenix,
            matches_phoenix,
            "phoenix/permits.json",
            PHOENIX_PAGE,
            query,
            root,
            cap,
            hours,
            network,
            transport,
            fresh,
        )
    if source_id == "tucson_permits":
        return _arc_pages(
            "tucson_permits",
            TUCSON_ENDPOINT,
            tucson_params,
            parse_tucson,
            matches_tucson,
            "tucson/permits.json",
            TUCSON_PAGE,
            query,
            root,
            cap,
            hours,
            network,
            transport,
            fresh,
        )
    return [], None


def _sam_once(query, root, cap, hours, network, transport, fresh=False):
    try:
        records = _cached_call(
            "sam",
            SAM_ENDPOINT,
            sam_params(query, cap),
            _sam_headers(),
            parse_sam,
            "sam/entities.json",
            root,
            cap,
            hours,
            network,
            transport,
            _sam_key(network),
            fresh,
        )
    except SourceFailure as exc:
        if exc.kind == "rate":
            return [], SAM_DAILY
        return [], exc.text
    return [record for record in records if matches_sam(record, query)], None


def _sam_pages(query, root, cap, hours, network, transport, budget, fresh=False):
    """One Arizona query, then keep the metro cities. Stop at the page budget."""
    kept = []
    pages = max(1, budget)
    for page in range(pages):
        try:
            records = _cached_call(
                "sam",
                SAM_ENDPOINT,
                sam_params(query, SAM_PAGE_SIZE, page),
                _sam_headers(),
                parse_sam,
                "sam/entities.json",
                root,
                cap,
                hours,
                network,
                transport,
                _sam_key(network),
                fresh,
            )
        except SourceFailure as exc:
            if exc.kind == "rate":
                return kept[:cap], SAM_DAILY
            if kept:
                return kept[:cap], exc.text
            return [], exc.text
        kept.extend(record for record in records if matches_sam(record, query))
        if len(records) < SAM_PAGE_SIZE or len(kept) >= cap:
            break
    return kept[:cap], None


def _arc_pages(source_id, endpoint, params_fn, parse, match, fixture, page_size, query, root, cap, hours, network, transport, fresh=False):
    kept = []
    offset = 0
    while len(kept) < cap:
        count = min(page_size, cap - len(kept))
        try:
            records = _cached_call(
                source_id,
                endpoint,
                params_fn(query, count, offset),
                {"Accept": "application/json"},
                parse,
                fixture,
                root,
                cap,
                hours,
                network,
                transport,
                "",
                fresh,
            )
        except SourceFailure as exc:
            if kept:
                return kept[:cap], exc.text
            return [], exc.text
        kept.extend(record for record in records if match(record, query))
        if len(records) < count:
            break
        offset += count
    return kept[:cap], None


def _markets(profile, filt, root, hours, network, transport):
    selected = {city.casefold() for city in filt.cities}
    metros = list(profile.search.metros)
    reports = []
    message = ""
    if not metros:
        report, message = load_market(
            profile.search.county, filt.naics, filt.sizes, root, hours, network, transport
        )
        return ([report] if report else []), message
    for metro in metros:
        if selected and not any(city.casefold() in selected for city in metro.cities):
            continue
        county = CountyConfig(
            name=metro.county_name,
            state=metro.state,
            state_fips=metro.state_fips,
            county_fips=metro.county_fips,
        )
        report, failure = load_market(
            county, filt.naics, filt.sizes, root, hours, network, transport
        )
        if report:
            reports.append(report)
        elif failure and not message:
            message = failure
    return reports, message


def _enrich_edgar(records, root, hours, network, transport, today, freshness):
    names = []
    for record in records:
        key = normalize_name(record.business_name)
        if key and key not in names:
            names.append(record.business_name)
    if not names:
        return records, None
    try:
        payload = _tickers(root, hours, network, transport)
    except SourceFailure as exc:
        return records, exc.text
    filings: dict[str, date | None] = {}
    for name in names:
        cik = find_cik(payload, name)
        if cik is None:
            continue
        try:
            body = _submission(cik, root, hours, network, transport)
        except SourceFailure as exc:
            return attach_filings(records, filings, today, freshness), exc.text
        filings[normalize_name(name)] = parse_submission(body)
    return attach_filings(records, filings, today, freshness), None


def _tickers(root, hours, network, transport):
    if not network:
        _source_log(root, "edgar", TICKERS_URL, "ok", 0, 0, False)
        return json.loads(_fixture("edgar/company_tickers.json"))
    return json.loads(
        _cached_body(
            "edgar",
            TICKERS_URL,
            [],
            _edgar_headers(network),
            root,
            hours,
            transport,
            "edgar/company_tickers.json",
        )
    )


def _submission(cik, root, hours, network, transport) -> str:
    url = submissions_url(cik)
    if not network:
        _source_log(root, "edgar", url, "ok", 1, 0, False)
        path = repo_root() / "sample_data" / "source_fixtures" / "edgar" / f"CIK{cik}.json"
        if not path.is_file():
            return "{}"
        return path.read_text(encoding="utf-8")
    return _cached_body("edgar", url, [], _edgar_headers(network), root, hours, transport, "")


def _cached_call(source, endpoint, params, headers, parser, fixture, root, cap, hours, network, transport, api_key, fresh=False):
    if not network:
        started = time.perf_counter()
        records = parser(_fixture(fixture))[:cap]
        _source_log(
            root,
            source,
            endpoint,
            "ok",
            len(records),
            _millis(started),
            False,
        )
        return records
    body = _cached_body(source, endpoint, params, headers, root, hours, transport, fixture, api_key, fresh)
    records = parser(body)
    return records[:cap]


def _cached_body(source, endpoint, params, headers, root, hours, transport, fixture, api_key="", fresh=False):
    material = endpoint + "|" + urllib.parse.urlencode(params)
    path = cache_file(root, source, material)
    cached = None if fresh else read_cache(path, hours)
    if cached is not None:
        try:
            count = _count_body(source, cached)
        except (ValueError, json.JSONDecodeError):
            count = 0
        _source_log(root, source, endpoint, "ok", count, 0, True)
        return cached
    wire = list(params)
    if api_key:
        wire.append(("api_key", api_key))
    started = time.perf_counter()
    try:
        status, body = transport(endpoint, wire, headers, TIMEOUT_SECONDS)
    except TimeoutError:
        _source_log(root, source, endpoint, "fail", 0, _millis(started), False)
        raise SourceFailure(source, "timeout") from None
    except OSError:
        _source_log(root, source, endpoint, "fail", 0, _millis(started), False)
        raise SourceFailure(source, "down") from None
    elapsed = _millis(started)
    if status == 429 or (source == "sam" and _sam_limited(body)):
        _source_log(root, source, endpoint, "fail", 0, elapsed, False)
        raise SourceFailure(source, "rate")
    if status != 200:
        _source_log(root, source, endpoint, "fail", 0, elapsed, False)
        raise SourceFailure(source, "down")
    clean = scrub(body)
    try:
        count = _count_body(source, clean)
    except (ValueError, json.JSONDecodeError):
        _source_log(root, source, endpoint, "fail", 0, elapsed, False)
        raise SourceFailure(source, "down")
    write_cache(path, clean)
    _source_log(root, source, endpoint, "ok", count, elapsed, False)
    return clean


def _sam_limited(body: str) -> bool:
    if "entityData" in body:
        return False
    text = body.casefold()
    return "daily" in text or "throttl" in text or "rate limit" in text


def _count_body(source: str, body: str) -> int:
    if source == "sam":
        return len(parse_sam(body))
    if source == "phoenix_permits":
        return len(parse_phoenix(body))
    if source == "edgar" and body.strip().startswith("{"):
        data = json.loads(body)
        if "filings" in data or "cik" in data:
            return 1
        if isinstance(data, dict):
            return len([value for value in data.values() if isinstance(value, dict)])
    return 0


def _sam_key(network: bool) -> str:
    if not network:
        return ""
    import os

    key = os.environ.get("SAM_API_KEY", "").strip()
    if not key:
        raise SourceFailure("sam", "sam_key")
    return key


def _sam_headers() -> dict[str, str]:
    return {"Accept": "application/json"}


def _edgar_headers(network: bool) -> dict[str, str]:
    import os

    headers = {"Accept": "application/json"}
    if not network:
        return headers
    agent = os.environ.get("LEADGEN_EDGAR_USER_AGENT", "").strip()
    if not agent:
        raise SourceFailure("edgar", "edgar_agent")
    headers["User-Agent"] = agent
    return headers


def _mark(record: PublicRecord, windows: dict[str, int], today: date) -> PublicRecord:
    data = record.model_dump()
    data["recent_permit"] = bool(
        record.recent_permit
        or within_window(record.permit_date, windows.get(record.source, 0), today)
    )
    data["recent_filing"] = bool(
        record.recent_filing or within_window(record.filing_date, windows.get("edgar", 0), today)
    )
    return PublicRecord.model_validate(data)


def _rank(profile, pipeline, records, filt, today) -> list[SearchHit]:
    windows = {spec.id: spec.freshness_days for spec in profile.search.sources}
    hits = []
    for record in records:
        prospect = prospect_from_record(profile, record, today)
        result = score(prospect, profile, pipeline)
        hits.append(
            SearchHit(
                record,
                main_label(record),
                is_stale(record, windows.get(record.source, 0), today),
                _fit(record, filt),
                result.total,
                "",
                prospect,
            )
        )
    hits.sort(
        key=lambda hit: (
            -hit.score,
            -_latest(hit.record).toordinal(),
            -hit.fit,
            hit.business_name,
            hit.prospect_id,
        )
    )
    return hits


def _latest(record: PublicRecord) -> date:
    return record.permit_date or record.record_date or date.min


def _fit(record: PublicRecord, filt: SearchFilter) -> int:
    total = 0
    if filt.naics and record.naics and any(code in record.naics for code in filt.naics):
        total += 1
    if filt.state and record.state.casefold() == filt.state.casefold():
        total += 1
    wanted = {city.casefold() for city in filt.cities}
    if wanted and record.city.casefold() in wanted:
        total += 1
    elif filt.city and record.city.casefold() == filt.city.casefold():
        total += 1
    if filt.business_type and any(
        item.casefold() == filt.business_type.casefold() for item in record.business_types
    ):
        total += 1
    if filt.permit_type and record.permit_type.casefold() == filt.permit_type.casefold():
        total += 1
    if filt.area and filt.area.casefold() in record.mailing_address.casefold():
        total += 1
    if record.recent_filing:
        total += 1
    if record.recent_permit:
        total += 1
    return total


def prospect_from_record(profile: Profile, record: PublicRecord, today: date) -> Prospect:
    if record.record_date is None:
        engaged = 9999
    else:
        engaged = max(0, (today - record.record_date).days)
    source = (
        record.source
        if record.source in {"sam", "edgar", "phoenix_permits", "tucson_permits"}
        else "sam"
    )
    return Prospect(
        prospect_id=_prospect_id(record),
        profile_id=profile.profile_id,
        contact_name=record.contact_name,
        organization=record.business_name or None,
        email="",
        region=record.city or record.state,
        source=source,
        last_engaged_days=engaged,
        consent_status="existing_relationship",
        do_not_contact=False,
        notes=_notes(record),
        attributes=_record_attributes(profile, record, today),
        phone=record.phone,
        mailing_address=record.mailing_address,
        contact_title=record.contact_title,
    )


def _notes(record: PublicRecord) -> str:
    parts = []
    if record.project:
        parts.append(f"Project: {record.project}.")
    if record.mailing_address:
        parts.append(f"Mailing address: {record.mailing_address}.")
    if record.contact_title:
        parts.append(f"Title: {record.contact_title}.")
    if record.phone:
        parts.append(f"Phone: {record.phone}.")
    if record.naics:
        parts.append("NAICS: " + ", ".join(record.naics) + ".")
    if record.permit_count > 1:
        parts.append(f"{record.permit_count} permits are on record.")
    if record.recent_filing:
        parts.append("A recent public filing is on record.")
    if record.recent_permit:
        parts.append("A recent permit is on record.")
    return " ".join(parts)


def _prospect_id(record: PublicRecord) -> str:
    raw = record.uei or record.source_record_id or record.business_name
    safe = "".join(character for character in raw if character.isalnum())[:20] or "record"
    prefix = {"sam": "SAM", "edgar": "EDG", "phoenix_permits": "PHX", "tucson_permits": "TUC"}.get(
        record.source, "PUB"
    )
    return f"{prefix}-{safe}"


# A live model call takes several seconds. Only the rows a person sees first get a written reason.
REASON_LIMIT = 5


def _fill_reasons(hits, request, profile, root) -> None:
    for hit in hits[:REASON_LIMIT]:
        prompt = reason_prompt(request, _fact_lines(hit.record))
        sentence = _one_reason(root, profile, prompt, hit.record, 1, None)
        if sentence is None:
            sentence = _one_reason(
                root,
                profile,
                prompt,
                hit.record,
                2,
                "The reason cited a value that is not on the record.",
            )
        hit.reason = sentence or ""


def _one_reason(root, profile, prompt, record, attempt, retry_reason):
    try:
        text = _model(root, profile, "reason", prompt, attempt, retry_reason)
    except (FileNotFoundError, ProviderError, OSError):
        return ""
    sentence = _parse_reason(text)
    if reason_is_grounded(sentence, record):
        return sentence
    return None


def _parse_reason(text: str) -> str:
    stripped = _strip_fence(text).strip()
    if stripped.startswith("{"):
        try:
            return str(json.loads(stripped).get("reason") or "").strip()
        except json.JSONDecodeError:
            return stripped
    return stripped


def _model(root, profile, role, prompt, attempt, retry_reason):
    if attempt > 1:
        _log(
            root,
            "search",
            "retry",
            role,
            "ok",
            retry_reason or "",
            attempt_number=attempt,
            retry_of=role,
            retry_reason=retry_reason or "",
        )
    result = complete(role, prompt, profile.profile_id, "search", attempt, root)
    fields = {
        "attempt_number": attempt,
        "provider": result.provider,
        "model": result.model,
        "duration_ms": result.duration_ms,
        "input_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    if attempt > 1:
        fields["retry_of"] = role
        fields["retry_reason"] = retry_reason or ""
    _log(root, "search", "model_call", role, "ok", role, **fields)
    return result.text


def _source_log(root, source, endpoint, status, records, duration_ms, cache_hit) -> None:
    detail = "ok" if status == "ok" else SourceFailure(source, "down").text
    if status == "fail":
        detail = "The source did not return records."
    _log(
        root,
        "search",
        "source_call",
        source,
        status,
        scrub(detail),
        endpoint=endpoint,
        record_count=records,
        cache_hit=cache_hit,
        duration_ms=duration_ms,
    )


def _query(filt: SearchFilter) -> SourceQuery:
    return SourceQuery(
        naics=list(filt.naics),
        state=filt.state,
        city=filt.city,
        cities=list(filt.cities),
        business_type=filt.business_type,
        permit_type=filt.permit_type,
        date_from=filt.date_from,
        date_to=filt.date_to,
        area=filt.area,
    )


def _keep_many(values, allowed, unsupported) -> list[str]:
    kept = []
    allowed_set = set(allowed)
    for value in values:
        if value in allowed_set and value not in kept:
            kept.append(value)
        elif value not in allowed_set and value.strip():
            unsupported.append(value)
    return kept


def _keep_one(value, allowed, unsupported) -> str:
    text = value.strip()
    if not text:
        return ""
    if text in allowed:
        return text
    unsupported.append(text)
    return ""


def _fixture(name: str) -> str:
    path = repo_root() / "sample_data" / "source_fixtures" / name
    return path.read_text(encoding="utf-8")


def _network(network: bool | None) -> bool:
    if network is not None:
        return network
    from leadgen.llm import current_mode

    return current_mode() == "live"


def _millis(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _record_attributes(profile: Profile, record: PublicRecord, today: date | None = None) -> dict:
    declared = profile.attributes
    cities = {
        city.casefold()
        for metro in profile.search.metros
        for city in metro.cities
    }
    if not cities:
        cities = {city.casefold() for city in profile.search.cities}
    values = {
        "in_service_area": "yes" if record.city.casefold() in cities else "no",
        "named_contact": "yes" if record.contact_name.strip() else "no",
        "target_industry_match": "yes" if record.naics else "no",
    }
    return {key: value for key, value in values.items() if key in declared}


def _fact_lines(record: PublicRecord) -> str:
    rows = [
        f"business_name: {record.business_name}",
        f"city: {record.city}",
        f"state: {record.state}",
        f"contact_name: {record.contact_name}",
        f"contact_title: {record.contact_title}",
        f"phone: {record.phone}",
        f"mailing_address: {record.mailing_address}",
        f"naics: {', '.join(record.naics)}",
        f"project: {record.project}",
        f"permit_type: {record.permit_type}",
        f"permit_count: {record.permit_count}",
        f"recent_filing: {record.recent_filing}",
        f"recent_permit: {record.recent_permit}",
    ]
    return "\n".join(rows)


def probe_lines(root: Path | None = None) -> list[str]:
    """One live search per profile. Counts and seconds only."""
    import os

    from leadgen.llm import load_project_env
    from leadgen.profiles import load_profile

    load_project_env()
    folder = Path(root) if root is not None else repo_root()
    lines = []
    if not os.environ.get("SAM_API_KEY", "").strip():
        lines.append("SAM_API_KEY: no. Live search skipped.")
        return lines
    if not os.environ.get("LEADGEN_EDGAR_USER_AGENT", "").strip():
        lines.append("LEADGEN_EDGAR_USER_AGENT: no. Live search skipped.")
        return lines
    lines.append("SAM_API_KEY: yes")
    lines.append("LEADGEN_EDGAR_USER_AGENT: yes")
    pipeline = load_pipeline_config()
    folder_ids = sorted(
        path.stem for path in (repo_root() / "config" / "profiles").glob("*.yaml")
    )
    for profile_id in folder_ids:
        profile = load_profile(profile_id)
        started = time.perf_counter()
        counts: list[tuple[str, int, int]] = []

        def watch(source, endpoint, status, records, duration_ms, cache_hit, bucket=counts):
            bucket.append((source, records, duration_ms))

        outcome = _probe_one(profile, pipeline, folder, watch)
        elapsed = time.perf_counter() - started
        for source, records, duration_ms in counts:
            lines.append(f"{profile.profile_id} {source} {records} records {duration_ms / 1000:.1f}s")
        for message in outcome.messages:
            lines.append(f"{profile.profile_id} {message}")
        lines.append(
            f"{profile.profile_id} shown {outcome.shown} held {outcome.held_back} "
            f"named {outcome.named_contacts} {elapsed:.1f}s"
        )
    return lines


def _probe_one(profile, pipeline, root, watch) -> SearchOutcome:
    """Search configured sources with allowlisted values. No model call and no record text."""
    global _source_log
    specs = profile.search.sources
    filt = SearchFilter(
        sources=[spec.id for spec in specs],
        naics=list(profile.search.naics[:1]),
        state=profile.search.states[0] if profile.search.states else "",
        city=profile.search.cities[0] if profile.search.cities else "",
        business_type=profile.search.business_types[0] if profile.search.business_types else "",
        permit_type=profile.search.permit_types[0] if profile.search.permit_types else "",
        area=profile.search.areas[0] if profile.search.areas else "",
    )
    permit_days = next((spec.freshness_days for spec in specs if spec.id == "phoenix_permits"), 0)
    if permit_days:
        filt = filt.model_copy(
            update={
                "date_from": (date.today() - _days(permit_days)).isoformat(),
                "date_to": date.today().isoformat(),
            }
        )
    original = _source_log

    def wrapped(folder, source, endpoint, status, records, duration_ms, cache_hit):
        watch(source, endpoint, status, records, duration_ms, cache_hit)
        original(folder, source, endpoint, status, records, duration_ms, cache_hit)

    _source_log = wrapped
    try:
        return execute(
            profile,
            filt,
            [],
            root,
            pipeline=pipeline,
            network=True,
            lookup_cap=1,
        )
    finally:
        _source_log = original


def _days(count: int):
    return timedelta(days=count)
