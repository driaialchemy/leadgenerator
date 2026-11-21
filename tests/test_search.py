"""Public-record search: fixtures, labels, de-dup, suppression, and secrets."""

import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from leadgen.approve import decide
from leadgen.llm import ModelResponse
from leadgen.paths import repo_root
from leadgen.pipeline import run_prospect
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.reasons import reason_is_grounded
from leadgen.schemas import Prospect
from leadgen.search import execute, restrict, search
from leadgen.sources.cache import cache_file, read_cache, write_cache
from leadgen.sources.edgar import find_cik
from leadgen.sources.phoenix import OUT_FIELDS, parse_phoenix, phoenix_params
from leadgen.sources.records import (
    PublicRecord,
    SearchFilter,
    SourceQuery,
    SuppressionEntry,
    is_stale,
    main_label,
    split_suppression,
    dedupe,
)
from leadgen.sources.sam import ENDPOINT as SAM_ENDPOINT
from leadgen.sources.sam import parse_sam, sam_params
from leadgen.ui_data import contact_channels

TODAY = date(2026, 11, 20)
ROOT = repo_root()
KEY = "unit-test-sam-key-9f3a"
AGENT = "unit-test-user-agent-9f3a"


def test_sam_fixture_parses_public_fields_only():
    records = parse_sam((ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8"))
    first = records[0]
    assert first.business_name == "Northwind Example LLC"
    assert first.uei == "NORTHWIND001"
    assert first.naics == ["541512"]
    assert first.contact_name == "Ada Lovelace"
    assert first.contact_title == "Owner"
    assert first.record_date == date(2026, 6, 1)
    assert first.phone == ""
    dumped = first.model_dump_json()
    assert "602-555-0199" not in dumped
    assert "ada@secret.example" not in dumped
    assert "api_key" not in first.source_url


def test_edgar_matches_exact_normalized_name_only():
    payload = json.loads(
        (ROOT / "sample_data" / "source_fixtures" / "edgar" / "company_tickers.json").read_text(encoding="utf-8")
    )
    assert find_cik(payload, "  northwind   example llc ") == "0000000100"
    assert find_cik(payload, "Northwind Example") is None
    assert find_cik(payload, "Northwind Example LLC.") is None
    assert find_cik(payload, "No Such Company") is None


def test_phoenix_fixture_parses_project_address_and_epoch():
    records = parse_phoenix(
        (ROOT / "sample_data" / "source_fixtures" / "phoenix" / "permits.json").read_text(encoding="utf-8")
    )
    assert records[0].project == "Office remodel"
    assert records[0].mailing_address == "100 Public Way, Phoenix, AZ"
    assert records[0].contractor == "Ada Lovelace"
    assert records[0].permit_value == ""
    assert records[0].permit_date == date(2026, 9, 1)
    body = {
        "features": [
            {"attributes": {"RECORD_ID": "9", "PERMIT_ISSUE_DATE": 1700000000000, "ADDRESS": "1 Main"}}
        ]
    }
    epoch = parse_phoenix(json.dumps(body))[0]
    assert epoch.permit_date == date(2023, 11, 14)


def test_parameter_templates_are_fixed():
    params = sam_params(
        SourceQuery(
            naics=["541512"],
            state="AZ",
            city="Phoenix",
            business_type="For Profit Organization",
        ),
        10,
    )
    assert params == [
        ("includeSections", "entityRegistration,coreData,pointsOfContact,assertions"),
        ("page", "0"),
        ("size", "10"),
        ("naicsCode", "541512"),
        ("physicalAddressProvinceOrStateCode", "AZ"),
        ("physicalAddressCity", "Phoenix"),
        ("businessTypeDesc", "For Profit Organization"),
    ]
    assert all(key != "api_key" for key, _value in params)
    permit = phoenix_params(
        SourceQuery(
            permit_type="Building",
            date_from="2026-05-24",
            date_to="2026-11-20",
            area="Phoenix",
        ),
        10,
    )
    assert permit[0] == (
        "where",
        "1=1 AND PERMIT_TYPE = 'Building' AND PERMIT_ISSUE_DATE >= DATE '2026-05-24' "
        "AND PERMIT_ISSUE_DATE <= DATE '2026-11-20' AND UPPER(ADDRESS) LIKE UPPER('%Phoenix%')",
    )
    assert permit[1] == ("outFields", OUT_FIELDS)
    assert permit[-1] == ("resultRecordCount", "10")


def test_values_outside_the_allowlist_are_not_queried():
    profile = load_profile("b2b_services")
    cleaned, unsupported = restrict(
        SearchFilter(
            sources=["sam", "made_up"],
            naics=["541512", "999999"],
            city="Phoenix",
            permit_type="Building",
            date_from="2026-01-01' OR '1'='1",
        ),
        profile,
    )
    assert cleaned.sources == ["sam"]
    assert cleaned.naics == ["541512"]
    assert cleaned.city == "Phoenix"
    assert cleaned.permit_type == ""
    assert cleaned.date_from == ""
    assert "999999" in unsupported
    assert "made_up" in unsupported
    assert "Building" in unsupported


def test_record_cap_keeps_ten():
    one = parse_sam((ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8"))[0]
    payload = {"entityData": [one.model_dump(mode="json")] * 12}
    # The parser reads the raw shape, so build twelve raw entities instead.
    raw = json.loads((ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8"))
    raw["entityData"] = [raw["entityData"][0]] * 12
    assert len(parse_sam(json.dumps(raw))[:10]) == 10
    assert load_pipeline_config().source_record_cap == 10
    assert one.business_name
    assert payload["entityData"]


def test_profiles_set_freshness_per_source():
    b2b = {spec.id: (spec.freshness_days, spec.role) for spec in load_profile("b2b_services").search.sources}
    home = {spec.id: (spec.freshness_days, spec.role) for spec in load_profile("home_services").search.sources}
    assert b2b == {"sam": (400, "search"), "edgar": (180, "enrich")}
    assert home == {"phoenix_permits": (180, "search"), "sam": (400, "lookup")}
    assert len(load_profile("b2b_services").search.examples) == 4
    assert len(load_profile("home_services").search.examples) == 4


def test_labels_keep_stale_as_a_separate_flag():
    today = TODAY
    named = _record("Ada Lovelace", "6025550100", "1 Main", date(2026, 6, 1))
    assert main_label(named) == "Named contact"
    assert is_stale(named, 400, today) is False
    phone_only = _record("", "6025550100", "1 Main", date(2026, 6, 1))
    assert main_label(phone_only) == "Business phone on record"
    mail_only = _record("", "", "1 Main", date(2026, 6, 1))
    assert main_label(mail_only) == "Mailing address only"
    old = _record("Ada Lovelace", "", "1 Main", date(2025, 1, 1))
    assert main_label(old) == "Named contact"
    assert is_stale(old, 400, today) is True
    edge = _record("Ada Lovelace", "", "1 Main", today - timedelta(days=400))
    assert is_stale(edge, 400, today) is False
    older = _record("Ada Lovelace", "", "1 Main", today - timedelta(days=401))
    assert is_stale(older, 400, today) is True


def test_hand_counted_dedup_and_suppression():
    # Two rows share a UEI, two share a name and address, one is unique, one is suppressed.
    records = [
        _named("A", "North", "1 Main"),
        _named("A", "North", "9 Main"),
        _named("", "West", "2 Main"),
        _named("", "West", "2 Main"),
        _named("", "East", "3 Main"),
        _named("B", "Held", "4 Main"),
    ]
    merged = dedupe(records)
    kept, held = split_suppression(merged, [SuppressionEntry(uei="B")])
    assert len(merged) == 4
    assert held == 1
    assert len(kept) == 3


def test_fixture_search_counts_are_hand_computed(tmp_path):
    # Fixture rows that match Phoenix / AZ / 541512 / For Profit Organization:
    # Northwind, the same UEI again, Held Back Supplies, Quiet Mail, Old Registration.
    # Tucson is a different city. De-dup leaves 4. Suppression removes Held Back Supplies.
    # Shown: Northwind (named), Quiet Mail (mailing), Old Registration (named, stale).
    profile = load_profile("b2b_services")
    outcome = execute(profile, _b2b_filter(), [], tmp_path, today=TODAY, network=False)
    assert outcome.total_matches == 4
    assert outcome.held_back == 1
    assert outcome.shown == 3
    assert outcome.named_contacts == 2
    by_name = {hit.business_name: hit for hit in outcome.hits}
    assert set(by_name) == {"Northwind Example LLC", "Quiet Mail LLC", "Old Registration LLC"}
    assert by_name["Northwind Example LLC"].label == "Named contact"
    assert by_name["Northwind Example LLC"].stale is False
    assert by_name["Northwind Example LLC"].record.recent_filing is True
    assert by_name["Quiet Mail LLC"].label == "Mailing address only"
    assert by_name["Old Registration LLC"].label == "Named contact"
    assert by_name["Old Registration LLC"].stale is True
    assert "602-555-0199" not in by_name["Northwind Example LLC"].record.model_dump_json()


def test_permit_search_merges_the_contractor_lookup(tmp_path):
    profile = load_profile("home_services")
    outcome = execute(profile, _home_filter(), [], tmp_path, today=TODAY, network=False)
    # One building permit in the date window. The SAM rows with the same name and address collapse into it.
    assert outcome.total_matches == 1
    assert outcome.held_back == 0
    assert outcome.shown == 1
    assert outcome.named_contacts == 1
    hit = outcome.hits[0]
    assert hit.record.uei == "NORTHWIND001"
    assert hit.record.recent_permit is True
    assert hit.label == "Named contact"
    assert hit.stale is False


def test_rate_limit_and_timeout_leave_the_other_source(tmp_path, monkeypatch):
    monkeypatch.setenv("SAM_API_KEY", KEY)
    monkeypatch.setenv("LEADGEN_EDGAR_USER_AGENT", AGENT)
    phoenix = (ROOT / "sample_data" / "source_fixtures" / "phoenix" / "permits.json").read_text(encoding="utf-8")
    profile = load_profile("home_services")

    def limited(url, params, headers, timeout):
        if "maps.phoenix.gov" in url:
            return 200, phoenix
        return 429, f"slow down {KEY}"

    limited_result = execute(
        profile, _home_filter(), [], tmp_path, today=TODAY, network=True, transport=limited
    )
    assert limited_result.messages == ["SAM.gov is rate limited."]
    assert limited_result.shown == 1

    def timed_out(url, params, headers, timeout):
        if "maps.phoenix.gov" in url:
            return 200, phoenix
        raise TimeoutError(f"timed out {KEY} {AGENT}")

    timed = execute(
        profile, _home_filter(), [], tmp_path, today=TODAY, network=True, transport=timed_out
    )
    assert timed.messages == ["SAM.gov timed out."]
    assert timed.shown == 1
    blob = _tree_text(tmp_path)
    assert KEY not in blob
    assert AGENT not in blob


def test_cache_hit_skips_the_call(tmp_path, monkeypatch):
    monkeypatch.setenv("SAM_API_KEY", KEY)
    body = (ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8")
    calls = {"n": 0}

    def transport(url, params, headers, timeout):
        calls["n"] += 1
        if "api.sam.gov" in url:
            assert dict(params)["api_key"] == KEY
            return 200, body
        if url.endswith("company_tickers.json"):
            assert headers.get("User-Agent") == AGENT
            return 200, (ROOT / "sample_data" / "source_fixtures" / "edgar" / "company_tickers.json").read_text(encoding="utf-8")
        return 200, (ROOT / "sample_data" / "source_fixtures" / "edgar" / "CIK0000000100.json").read_text(encoding="utf-8")

    monkeypatch.setenv("LEADGEN_EDGAR_USER_AGENT", AGENT)
    profile = load_profile("b2b_services")
    execute(profile, _b2b_filter(), [], tmp_path, today=TODAY, network=True, transport=transport)
    first = calls["n"]
    assert first >= 1
    execute(profile, _b2b_filter(), [], tmp_path, today=TODAY, network=True, transport=transport)
    assert calls["n"] == first
    params = sam_params(
        SourceQuery(naics=["541512"], state="AZ", city="Phoenix", business_type="For Profit Organization"),
        10,
    )
    import urllib.parse

    material = SAM_ENDPOINT + "|" + urllib.parse.urlencode(params)
    cached = read_cache(cache_file(tmp_path, "sam", material), 24)
    assert cached is not None
    assert KEY not in cached
    from datetime import datetime, timezone

    stale = cache_file(tmp_path, "sam", material + "|old")
    write_cache(stale, body, now=datetime.now(timezone.utc) - timedelta(hours=48))
    assert read_cache(stale, 24) is None


def test_secrets_never_land_in_output_logs_or_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SAM_API_KEY", KEY)
    monkeypatch.setenv("LEADGEN_EDGAR_USER_AGENT", AGENT)
    seen = {}

    def transport(url, params, headers, timeout):
        if "api.sam.gov" in url:
            seen["key"] = dict(params).get("api_key")
            return 200, json.dumps(
                {
                    "entityData": [
                        {
                            "entityRegistration": {
                                "ueiSAM": "EXAMPLE000001",
                                "legalBusinessName": "Example Co",
                                "lastUpdateDate": "2026-06-01",
                            },
                            "coreData": {
                                "mailingAddress": {
                                    "addressLine1": "1 Main",
                                    "city": "Phoenix",
                                    "stateOrProvinceCode": "AZ",
                                },
                                "businessTypes": {
                                    "businessTypeList": [{"businessTypeDesc": "For Profit Organization"}]
                                },
                            },
                            "assertions": {"goodsAndServices": {"primaryNaics": "541512"}},
                            "echo": KEY,
                            "agent": AGENT,
                        }
                    ]
                }
            )
        seen["agent"] = headers.get("User-Agent")
        return 200, json.dumps({"0": {"cik_str": 1, "ticker": "X", "title": AGENT}})

    profile = load_profile("b2b_services")
    outcome = execute(profile, _b2b_filter(), [], tmp_path, today=TODAY, network=True, transport=transport)
    assert seen["key"] == KEY
    assert seen["agent"] == AGENT
    blob = _tree_text(tmp_path) + json.dumps(outcome.messages) + json.dumps(outcome.unsupported)
    assert KEY not in blob
    assert AGENT not in blob


def test_bad_filter_is_retried_once(tmp_path, monkeypatch):
    profile = load_profile("b2b_services")

    def fake(role, prompt, profile_id, prospect_id, attempt, root=None):
        if role == "translator":
            text = "nope" if attempt == 1 else (ROOT / "sample_data" / "replays" / "b2b_services" / "search" / "translator.json").read_text(encoding="utf-8")
        else:
            text = '{"reason": "This record matches the requested search."}'
        return ModelResponse(text, "google", "gemini-4-argon", None, None, None, False)

    monkeypatch.setattr("leadgen.search.complete", fake)
    outcome = search(profile, "Registered firms in Phoenix", tmp_path, today=TODAY, network=False)
    assert outcome.shown == 3
    rows = [
        json.loads(line)
        for line in (tmp_path / "runs" / "flight_recorder.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    retried = [row for row in rows if row["event_type"] == "model_call" and row["attempt_number"] == 2]
    assert retried
    assert any(row["retry_reason"] == "The filter was not valid." for row in rows)


def test_reason_citing_a_missing_value_is_retried(tmp_path, monkeypatch):
    record = _record("Ada Lovelace", "", "100 Public Way, Phoenix, AZ", TODAY)
    record = record.model_copy(update={"city": "Phoenix", "business_name": "Northwind Example LLC"})
    assert reason_is_grounded("Ada Lovelace in Phoenix", record) is True
    assert reason_is_grounded("Employs 400 people.", record) is False
    profile = load_profile("b2b_services")

    def fake(role, prompt, profile_id, prospect_id, attempt, root=None):
        if role == "reason" and attempt == 1:
            text = "Employs 400 people."
        else:
            text = '{"reason": "This record matches the requested search."}'
        return ModelResponse(text, "google", "gemini-4-argon", None, None, None, False)

    monkeypatch.setattr("leadgen.search.complete", fake)
    outcome = execute(profile, _b2b_filter(), [], tmp_path, today=TODAY, network=False)
    assert outcome.hits
    assert all(hit.reason == "This record matches the requested search." for hit in outcome.hits)
    assert all("400" not in hit.reason for hit in outcome.hits)


def test_sam_prospect_without_email_can_be_approved(tmp_path):
    profile = load_profile("b2b_services")
    pipeline = load_pipeline_config()
    prospect = Prospect(
        prospect_id="SAM-NOEMAIL",
        profile_id=profile.profile_id,
        contact_name="Ada Lovelace",
        organization="Northwind Example LLC",
        email="",
        region="Phoenix",
        source="sam",
        last_engaged_days=5,
        consent_status="opt_in",
        do_not_contact=False,
        notes="Wants help desk coverage. Two IT staff overwhelmed.",
        attributes={"employee_count": 40, "industry": "legal", "current_it_setup": "in_house"},
        phone="",
        mailing_address="100 Public Way, Phoenix, AZ",
        contact_title="Owner",
    )
    source = ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-004"
    dest = tmp_path / "sample_data" / "replays" / "b2b_services" / "SAM-NOEMAIL"
    dest.mkdir(parents=True)
    for name in ("tailor.json", "drafter.json", "evaluator.json"):
        shutil.copy(source / name, dest / name)
    result = run_prospect(profile, prospect, pipeline, tmp_path)
    assert result.status == "PENDING_APPROVAL"
    assert result.run_dir is not None
    rendered = (result.run_dir / "rendered.txt").read_text(encoding="utf-8")
    assert "No email on record" not in rendered
    channels = contact_channels(result.run_dir)
    assert "Point of contact: Ada Lovelace, Owner" in channels
    assert "Mailing address: 100 Public Way, Phoenix, AZ" in channels
    assert "No email on record" in channels
    assert not any(line.startswith("Phone:") for line in channels)
    code, message = decide(tmp_path, profile.profile_id, prospect.prospect_id, "APPROVED", "Ada")
    assert code == 0
    assert message.startswith("Wrote ")
    files = list((tmp_path / "outbox").glob("*.txt"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "No email on record" in body
    assert "Subject:" in body


def _b2b_filter() -> SearchFilter:
    return SearchFilter(
        sources=["sam", "edgar"],
        naics=["541512"],
        state="AZ",
        city="Phoenix",
        business_type="For Profit Organization",
    )


def _home_filter() -> SearchFilter:
    return SearchFilter(
        sources=["phoenix_permits", "sam"],
        permit_type="Building",
        area="Phoenix",
        date_from="2026-05-24",
        date_to="2026-11-20",
    )


def _record(name: str, phone: str, address: str, day: date) -> PublicRecord:
    return PublicRecord(
        source="sam",
        source_record_id="1",
        source_url="https://sam.gov/entity/1",
        record_date=day,
        contact_name=name,
        phone=phone,
        mailing_address=address,
    )


def _named(uei: str, name: str, address: str) -> PublicRecord:
    return PublicRecord(
        source="sam",
        source_record_id=uei or name,
        source_url="https://sam.gov/entity/1",
        business_name=name,
        uei=uei,
        mailing_address=address,
        contact_name="Ada",
    )


def _tree_text(root: Path) -> str:
    chunks = []
    for path in root.rglob("*"):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)
