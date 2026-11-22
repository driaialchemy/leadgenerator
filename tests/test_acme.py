"""Acme Plumbing search, shortlist, price check, and send gate."""

import json
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from leadgen.json_text import parse_model_json
from leadgen.mail import deliver
from leadgen.paths import repo_root
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.renderer import render
from leadgen.schemas import DraftEmail, EvidenceQuote, EvaluatorResult, Prospect, TailorResult
from leadgen.search import SAM_DAILY, parse_filter, restrict, search
from leadgen.shortlist import add_shortlist, load_shortlist
from leadgen.sources.records import SearchFilter
from leadgen.ui_data import search_view
from leadgen.verifier import verify

ROOT = repo_root()
APP = ROOT / "src" / "leadgen" / "app.py"
TODAY = date(2026, 11, 21)


def test_fenced_and_extra_keys_parse_and_bad_values_are_rejected():
    profile = load_profile("acme_plumbing")
    fenced = 'Sure.\n```json\n{"naics": ["541512"], "sources": ["sam"], "bonus": true}\n```\nDone'
    prose = 'The filter is {"naics": ["722511"], "sizes": ["1-49"], "note": "hi"} thanks'
    plain = '{"naics": ["721110"], "state": "AZ"}'
    assert parse_filter(fenced).naics == ["541512"]
    assert parse_filter(prose).naics == ["722511"]
    assert parse_filter(plain).naics == ["721110"]
    kept, dropped = restrict(parse_filter(fenced), profile)
    assert kept.naics == ["541512"]
    bad, unsupported = restrict(
        SearchFilter(naics=["999999"], sizes=["giant"], state="ZZ", sources=["sam"]),
        profile,
    )
    assert bad.naics == []
    assert bad.sizes == []
    assert bad.state == ""
    assert "999999" in unsupported
    assert "giant" in unsupported
    with pytest.raises(Exception):
        parse_model_json("this is not json", SearchFilter)
    scored = parse_model_json('{"relevance": 5, "specificity": 4, "clarity": 4, "tone": 5, "suggestions": ["shorter"], "extra": 1}', EvaluatorResult)
    assert scored.relevance == 5


def test_translator_failure_still_searches_the_fields(tmp_path, monkeypatch):
    profile = load_profile("acme_plumbing")

    def boom(*_args, **_kwargs):
        raise ValueError("not json")

    monkeypatch.setattr("leadgen.search.translate", boom)
    outcome = search(
        profile,
        "restaurants near the shop",
        tmp_path,
        today=TODAY,
        network=False,
        chosen_naics=["722511"],
        chosen_cities=_both_cities(profile),
    )
    assert any("could not be read" in message for message in outcome.messages)
    assert outcome.filter.sources
    assert "sources none" not in " ".join(outcome.messages)
    assert outcome.filter.naics == ["722511"]
    assert any(hit.record.city == "Phoenix" for hit in outcome.hits)
    assert any(hit.record.city == "Tucson" for hit in outcome.hits)


def test_search_with_no_industry_covers_both_metros_and_reports_status(tmp_path):
    profile = load_profile("acme_plumbing")
    outcome = search(
        profile,
        "",
        tmp_path,
        today=TODAY,
        network=False,
        chosen_cities=_both_cities(profile),
    )
    assert outcome.filter.naics == []
    assert outcome.filter.sources
    cities = {hit.record.city for hit in outcome.hits}
    assert "Phoenix" in cities
    assert "Tucson" in cities
    assert outcome.statuses
    assert all(line.strip() for line in outcome.statuses)
    assert len(outcome.hits) <= load_pipeline_config().source_record_cap


def test_sam_queries_arizona_once_and_stops_at_the_daily_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SAM_API_KEY", "test-key-value")
    profile = load_profile("acme_plumbing")
    fixture = json.loads((ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8"))
    seed = fixture["entityData"][0]
    page = []
    for index, city in enumerate(["Phoenix", "Tucson", "Flagstaff"] * 4):
        item = json.loads(json.dumps(seed))
        item["entityRegistration"]["ueiSAM"] = f"UEI{index:04d}"
        item["entityRegistration"]["legalBusinessName"] = f"Firm {index}"
        for key in ("physicalAddress", "mailingAddress"):
            address = item["coreData"].setdefault(key, {})
            address["city"] = city
            address["stateOrProvinceCode"] = "AZ"
        page.append(item)
    seen = []

    def transport(url, params, headers, timeout):
        if "api.sam.gov" in url:
            query = dict(params)
            seen.append(query)
            assert "physicalAddressCity" not in query
            assert query.get("physicalAddressProvinceOrStateCode") == "AZ"
            if query.get("page") == "0":
                return 200, json.dumps({"entityData": page})
            return 429, "daily limit"
        if "maps.phoenix.gov" in url:
            return 200, (ROOT / "sample_data" / "source_fixtures" / "phoenix" / "permits.json").read_text(encoding="utf-8")
        if "mapdata.tucsonaz.gov" in url:
            return 200, (ROOT / "sample_data" / "source_fixtures" / "tucson" / "permits.json").read_text(encoding="utf-8")
        if url.endswith("company_tickers.json"):
            return 200, (ROOT / "sample_data" / "source_fixtures" / "edgar" / "company_tickers.json").read_text(encoding="utf-8")
        return 200, "{}"

    outcome = search(
        profile,
        "",
        tmp_path,
        today=TODAY,
        network=True,
        transport=transport,
        chosen_cities=_both_cities(profile),
    )
    pages = [item.get("page") for item in seen if "page" in item]
    assert pages == ["0", "1"]
    assert SAM_DAILY in outcome.statuses
    names = {hit.business_name for hit in outcome.hits}
    assert "Firm 0" in names or any(name.startswith("Firm ") for name in names)
    assert "Flagstaff" not in {hit.record.city for hit in outcome.hits}
    assert any(hit.record.city in {"Phoenix", "Tucson"} for hit in outcome.hits)


def test_industry_words_match():
    from leadgen.industry import suggest

    expected = {
        "cellular": "517112",
        "plumbr": "238220",
        "restraunt": "722511",
        "property managment": "531312",
        "hotel": "721110",
    }
    for text, code in expected.items():
        matches = suggest(text)
        assert matches and matches[0].confident
        assert matches[0].code == code


def test_add_all_shown_stores_names_once(tmp_path):
    profile = load_profile("acme_plumbing")
    outcome = search(profile, "", tmp_path, today=TODAY, network=False, chosen_cities=_both_cities(profile))
    view = search_view(outcome)
    rows = []
    prospects = {item["prospect_id"]: item for item in view["prospects"]}
    for row in view["rows"]:
        rows.append({**row, "profile_id": profile.profile_id, "prospect": prospects[row["prospect_id"]]["prospect"]})
    add_shortlist(tmp_path, rows)
    add_shortlist(tmp_path, rows)
    stored = load_shortlist(tmp_path)
    assert len(stored) == len(rows)
    assert stored
    assert all(row.get("business") for row in stored)
    assert all("prospect_id" not in row["business"] for row in stored)


def test_approved_price_passes_and_another_price_or_discount_is_blocked():
    profile = load_profile("acme_plumbing")
    pipeline = load_pipeline_config()
    prospect = _prospect()
    tailor = TailorResult(
        prospect_id=prospect.prospect_id,
        claim_ids=["RATE-01"],
        evidence=[EvidenceQuote(claim_id="RATE-01", quote="Asked for a walkthrough")],
    )
    draft = _draft(prospect, "You asked for a walkthrough of the line.", "We can set a time to walk the property.")
    report = verify(tailor, draft, prospect, profile, pipeline)
    assert report.passed
    body = render(draft, prospect, profile).body
    assert "$150 per hour plus parts" in body
    discounted = _draft(prospect, "You asked for a walkthrough and a discount.", "We can set a time.")
    blocked = verify(tailor, discounted, prospect, profile, pipeline)
    assert not blocked.passed
    assert any(issue.code == "banned_phrase" for issue in blocked.blocking)
    priced = _draft(prospect, "You asked for a walkthrough at $99 an hour.", "We can set a time.")
    other = verify(tailor, priced, prospect, profile, pipeline)
    assert not other.passed
    assert any(issue.code == "digits" for issue in other.blocking)


def test_placeholder_sender_blocks_send_and_allows_drafts(tmp_path):
    run = _approved_run(tmp_path)
    client = _Mailbox()
    drafted = deliver(tmp_path, run, "gmail", "draft", client=client)
    assert drafted.ok
    practiced = deliver(tmp_path, run, "practice", "draft", client=client)
    assert practiced.ok
    refused = deliver(tmp_path, run, "gmail", "send", confirmed=True, demo_safety=False, client=client)
    assert not refused.ok
    assert refused.message == (
        "Add Acme's real sender name, address, and phone in the settings file before sending"
    )
    assert all(call[0] != "send" for call in client.calls)


def test_screen_has_no_picker_and_shortlist_uses_names(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception
    text = _text(at)
    assert "Red-team" not in text
    assert "Practice data" not in text
    assert "B2B-" not in text
    assert "HOME-" not in text
    assert at.sidebar.selectbox == [] or all(box.label != "Business" for box in at.sidebar.selectbox)
    at.button(key="search").click().run()
    assert not at.exception
    at.button(key="add_all").click().run()
    assert not at.exception
    _switch(at, "shortlist")
    shown = _text(at)
    assert "B2B-" not in shown
    assert "Congress Kitchen" in shown or "Northwind Example LLC" in shown


class _Mailbox:
    def __init__(self):
        self.account = "owner@example.com"
        self.calls = []

    def draft(self, recipient, subject, body, account):
        self.calls.append(("draft", recipient, subject, body, account))
        return "draft-1"

    def send(self, recipient, subject, body, account):
        self.calls.append(("send", recipient, subject, body, account))
        return "sent-1"


def _approved_run(tmp_path: Path) -> Path:
    profile = load_profile("acme_plumbing")
    run = tmp_path / "runs" / "ACME-1"
    run.mkdir(parents=True)
    body = "\n".join(
        [
            "Hi Riley,",
            profile.sender.name,
            profile.sender.company,
            profile.sender.postal_address,
            profile.sender.phone,
            profile.opt_out_line,
        ]
    )
    rendered = f"Subject: A short hello\n\n{body}\n"
    (run / "rendered.txt").write_text(rendered, encoding="utf-8")
    (run / "prospect.json").write_text(
        json.dumps({"email": "riley@example.com", "contact_name": "Riley Chen"}),
        encoding="utf-8",
    )
    (run / "status.json").write_text(
        json.dumps({"prospect_id": "SAM-RIVER", "profile_id": profile.profile_id, "status": "PENDING_APPROVAL"}),
        encoding="utf-8",
    )
    (run / "approval.json").write_text(
        json.dumps({"decision": "APPROVED", "name": "Ada", "ack_findings": False, "run_id": run.name}),
        encoding="utf-8",
    )
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / f"{run.name}.txt").write_text(rendered, encoding="utf-8")
    return run


def _both_cities(profile):
    cities = []
    for metro in profile.search.metros:
        cities.extend(metro.cities)
    return cities


def _prospect():
    return Prospect(
        prospect_id="SAM-RIVER",
        profile_id="acme_plumbing",
        contact_name="Riley Chen",
        organization="Congress Kitchen",
        email="riley@example.com",
        region="Tucson",
        source="sam",
        last_engaged_days=10,
        consent_status="existing_relationship",
        do_not_contact=False,
        notes="Asked for a walkthrough of the kitchen line.",
        attributes={
            "in_service_area": "yes",
            "named_contact": "yes",
            "recent_permit": "yes",
            "hiring_fit": "yes",
            "permit_recency": "d90",
            "plumbing_tie": "strong",
            "permit_count": "many",
        },
    )


def _draft(prospect, hook, bridge):
    return DraftEmail(
        prospect_id=prospect.prospect_id,
        subject_id="SUB-01",
        claim_ids=["RATE-01"],
        hook=hook,
        bridge=bridge,
    )


def _text(at) -> str:
    chunks = []
    for item in at.markdown:
        chunks.append(str(item.value))
    for item in at.info:
        chunks.append(str(item.value))
    for item in at.warning:
        chunks.append(str(item.value))
    for item in at.error:
        chunks.append(str(item.value))
    return "\n".join(chunks)


def _switch(at, step):
    at.session_state["step"] = step
    at.run()
