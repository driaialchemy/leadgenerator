"""Turn a plain-language request into a ranked public-record shortlist."""

import hashlib
import json
import time
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from leadgen.kill_switch import assert_not_engaged
from leadgen.llm import complete, scrub
from leadgen.messages import reason_prompt, translator_prompt
from leadgen.paths import repo_root
from leadgen.pipeline import _log
from leadgen.profiles import load_pipeline_config
from leadgen.schemas import PipelineConfig, Profile, Prospect
from leadgen.scoring import score
from leadgen.sources.cache import cache_file, read_cache, write_cache
from leadgen.sources.edgar import (
    TICKERS_URL,
    attach_filings,
    find_cik,
    parse_submission,
    submissions_url,
)
from leadgen.sources.phoenix import ENDPOINT as PHOENIX_ENDPOINT
from leadgen.sources.phoenix import matches_phoenix, parse_phoenix, phoenix_params
from leadgen.sources.records import (
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
    def __init__(self, hits, total_matches, named_contacts, shown, held_back, messages, unsupported, filt):
        self.hits = hits
        self.total_matches = total_matches
        self.named_contacts = named_contacts
        self.shown = shown
        self.held_back = held_back
        self.messages = messages
        self.unsupported = unsupported
        self.filter = filt


def search(
    profile: Profile,
    request: str,
    root: Path | None = None,
    pipeline: PipelineConfig | None = None,
    today: date | None = None,
    network: bool | None = None,
    transport=None,
    lookup_cap: int | None = None,
) -> SearchOutcome:
    """Rank public records for one request. A failed source does not stop the others."""
    folder = Path(root) if root is not None else repo_root()
    assert_not_engaged(folder)
    _log(folder, "search", "search", "search", "ok", scrub(request)[:240] or "search")
    try:
        filt, unsupported = translate(profile, request, folder)
    except (ValueError, json.JSONDecodeError, ValidationError):
        filt, unsupported = SearchFilter(), ["the request"]
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
) -> SearchOutcome:
    config = pipeline or load_pipeline_config()
    day = today or date.today()
    use_network = _network(network)
    caller = transport or fetch
    cap = config.source_record_cap
    hours = config.source_cache_hours
    windows = {spec.id: spec.freshness_days for spec in profile.search.sources}
    specs = {spec.id: spec for spec in profile.search.sources}
    messages: list[str] = []
    records: list[PublicRecord] = []
    query = _query(filt)
    for source_id in filt.sources:
        spec = specs.get(source_id)
        if spec is None or spec.role != "search":
            continue
        found, failure = _search_source(
            source_id, query, root, cap, hours, use_network, caller, day
        )
        if failure is not None:
            messages.append(failure)
            continue
        records.extend(found)
    if any(spec.role == "lookup" and spec.id in filt.sources for spec in profile.search.sources):
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
                messages.append(failure)
                break
            records.extend(found)
    merged = dedupe(records)
    if "edgar" in filt.sources:
        merged, failure = _enrich_edgar(
            merged, root, hours, use_network, caller, day, windows.get("edgar", 0)
        )
        if failure is not None:
            messages.append(failure)
    marked = [_mark(record, windows, day) for record in merged]
    kept, held_back = split_suppression(marked, load_suppression())
    hits = _rank(profile, config, kept, filt, day)
    _fill_reasons(hits, request, profile, root)
    named = sum(1 for hit in hits if hit.label == "Named contact")
    return SearchOutcome(
        hits=hits,
        total_matches=len(marked),
        named_contacts=named,
        shown=len(hits),
        held_back=held_back,
        messages=messages,
        unsupported=unsupported,
        filt=filt,
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
    return SearchFilter.model_validate(json.loads(_strip_fence(text)))


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
    naics = _keep_many(filt.naics, profile.search.naics, unsupported)
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


def _search_source(source_id, query, root, cap, hours, network, transport, today):
    if source_id == "sam":
        if not query.legal_name and not (query.naics or query.state or query.city or query.business_type):
            return [], "SAM.gov needs a NAICS code, state, city, or business type."
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
            )
        except SourceFailure as exc:
            return [], exc.text
        return [record for record in records if matches_sam(record, query)], None
    if source_id == "phoenix_permits":
        if not (query.permit_type or query.area or query.date_from or query.date_to):
            return [], "Phoenix permits needs a permit type, date range, or area."
        try:
            records = _cached_call(
                "phoenix_permits",
                PHOENIX_ENDPOINT,
                phoenix_params(query, cap),
                {"Accept": "application/json"},
                parse_phoenix,
                "phoenix/permits.json",
                root,
                cap,
                hours,
                network,
                transport,
                "",
            )
        except SourceFailure as exc:
            return [], exc.text
        return [record for record in records if matches_phoenix(record, query)], None
    return [], None


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


def _cached_call(source, endpoint, params, headers, parser, fixture, root, cap, hours, network, transport, api_key):
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
    body = _cached_body(source, endpoint, params, headers, root, hours, transport, fixture, api_key)
    records = parser(body)
    return records[:cap]


def _cached_body(source, endpoint, params, headers, root, hours, transport, fixture, api_key=""):
    material = endpoint + "|" + urllib.parse.urlencode(params)
    path = cache_file(root, source, material)
    cached = read_cache(path, hours)
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
    if status == 429:
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
        record.recent_permit or within_window(record.permit_date, windows.get("phoenix_permits", 0), today)
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
    hits.sort(key=lambda hit: (-hit.fit, -hit.score, hit.business_name, hit.prospect_id))
    return hits


def _fit(record: PublicRecord, filt: SearchFilter) -> int:
    total = 0
    if filt.naics and record.naics and any(code in record.naics for code in filt.naics):
        total += 1
    if filt.state and record.state.casefold() == filt.state.casefold():
        total += 1
    if filt.city and record.city.casefold() == filt.city.casefold():
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
    source = record.source if record.source in {"sam", "edgar", "phoenix_permits"} else "sam"
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
        attributes={},
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
    if record.recent_filing:
        parts.append("A recent public filing is on record.")
    if record.recent_permit:
        parts.append("A recent permit is on record.")
    return " ".join(parts)


def _prospect_id(record: PublicRecord) -> str:
    raw = record.uei or record.source_record_id or record.business_name
    safe = "".join(character for character in raw if character.isalnum())[:20] or "record"
    prefix = {"sam": "SAM", "edgar": "EDG", "phoenix_permits": "PHX"}.get(record.source, "PUB")
    return f"{prefix}-{safe}"


def _fill_reasons(hits, request, profile, root) -> None:
    for hit in hits:
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
    text = _model(root, profile, "reason", prompt, attempt, retry_reason)
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
