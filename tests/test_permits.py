"""Permit rows become businesses: names, relevance, de-duplication, contacts, and scores."""

from datetime import date
from pathlib import Path

from leadgen.permits import consolidate, recency_band, refine
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.scoring import score
from leadgen.search import parse_filter, prospect_from_record, restrict
from leadgen.sources.phoenix import parse_phoenix
from leadgen.sources.tucson import parse_tucson
from leadgen.ui_data import _summary

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 21)


def _profile():
    return load_profile("acme_plumbing")


def _phoenix():
    body = (FIX / "permits" / "phoenix_commercial.json").read_text(encoding="utf-8")
    return refine(parse_phoenix(body), _profile().search.permits)


def _tucson():
    body = (FIX / "permits" / "tucson_commercial.json").read_text(encoding="utf-8")
    return refine(parse_tucson(body), _profile().search.permits)


def _merged():
    kept = _phoenix()[0] + _tucson()[0]
    return {record.business_name: record for record in consolidate(kept)}


def test_translator_parses_the_captured_live_replies():
    profile = _profile()
    for name in ("live_reply_0.txt", "live_reply_1.txt"):
        text = (FIX / "translator" / name).read_text(encoding="utf-8")
        filt = parse_filter(text)
        assert filt.business_type == ""
        assert filt.permit_type == ""
        assert isinstance(filt.naics, list)
        restrict(filt, profile)
    second = parse_filter((FIX / "translator" / "live_reply_1.txt").read_text(encoding="utf-8"))
    assert second.naics == ["721110"]
    assert second.city == "Tucson"


def test_counts_for_excluded_and_dropped_rows_are_reported():
    _kept, phoenix = _phoenix()
    assert (phoenix.total, phoenix.excluded, phoenix.dropped, phoenix.kept) == (7, 2, 1, 4)
    assert phoenix.line("Phoenix permits") == (
        "Phoenix permits: 7 records \u00b7 2 left out, not commercial plumbing work"
        " \u00b7 1 dropped, no business name"
    )
    _kept, tucson = _tucson()
    assert (tucson.total, tucson.excluded, tucson.dropped, tucson.kept) == (8, 2, 2, 4)


def test_business_comes_from_a_company_field_or_a_valid_site_name():
    assert set(_merged()) == {
        "SUNSET HILLS ASSISTED LIVING",
        "Desert Pipe Works Inc",
        "Valley Fire+Security",
        "Valencia Auto Parts 10780",
        "Fontana Storage Hub",
        "Concert Place Performance Center",
    }


def test_intersections_addresses_and_descriptions_are_never_a_business():
    names = set(_merged())
    for bad in (
        "7TH & DEER VALLEY",
        "3 SIDEWALK PANELS ON SEC",
        "Automatic Gate w/ Key Switch, Card Reader Installation",
        "Modernize eq 1628",
        "1100 E Silverlake RD",
        "PRJ000427 Equip Well E-032A",
    ):
        assert bad not in names


def test_the_work_description_goes_in_project():
    merged = _merged()
    assert merged["SUNSET HILLS ASSISTED LIVING"].project == "Interior tenant improvement"
    assert merged["Desert Pipe Works Inc"].project == "Rough plumbing for a new building"
    assert (
        merged["Valencia Auto Parts 10780"].project
        == "New Construction of an auto parts retail store"
    )


def test_irrelevant_permit_types_are_excluded():
    kept = [record.site_name for record in _phoenix()[0] + _tucson()[0]]
    for gone in ("CORNER MART", "Perimeter Wall", "Eastside Congregation", "demo fire damaged unit"):
        assert gone not in kept


def test_duplicates_collapse_with_count_and_latest_date():
    merged = _merged()
    metro = merged["Valley Fire+Security"]
    assert metro.permit_count == 2
    assert metro.permit_date == date(2026, 11, 15)
    storage = merged["Fontana Storage Hub"]
    assert storage.permit_count == 2
    assert storage.permit_date == date(2026, 11, 1)
    assert merged["SUNSET HILLS ASSISTED LIVING"].permit_count == 1


def test_contact_is_a_person_only():
    merged = _merged()
    assert merged["SUNSET HILLS ASSISTED LIVING"].contact_name == "Sam Okafor"
    assert merged["Desert Pipe Works Inc"].contact_name == ""
    assert merged["Valley Fire+Security"].contact_name == ""
    assert merged["Valley Fire+Security"].contractor == "Valley Fire+Security"
    assert merged["Valencia Auto Parts 10780"].contact_name == ""


def test_scores_differ_and_match_hand_computed_values():
    profile = _profile()
    pipeline = load_pipeline_config()
    assert sum(rule.points for rule in profile.scoring_rules) == 100
    # area 20, contact 15, recency 25/18/10/3, plumbing tie 25/12, count 10/6/2.
    expected = {
        "SUNSET HILLS ASSISTED LIVING": 87,  # 20 + 15 + 25 (11 days) + 25 strong + 2 one permit
        "Valley Fire+Security": 76,  # 20 + 0 + 25 (6 days) + 25 strong + 6 two permits
        "Desert Pipe Works Inc": 65,  # 20 + 0 + 18 (112 days) + 25 strong + 2
        "Fontana Storage Hub": 63,  # 20 + 0 + 25 (20 days) + 12 some + 6
        "Valencia Auto Parts 10780": 59,  # 20 + 0 + 25 (2 days) + 12 + 2
        "Concert Place Performance Center": 44,  # 20 + 0 + 10 (195 days) + 12 + 2
    }
    got = {}
    for name, record in _merged().items():
        prospect = prospect_from_record(profile, record, TODAY)
        got[name] = score(prospect, profile, pipeline).total
    assert got == expected
    assert len(set(got.values())) == len(got)


def test_recency_bands():
    rules = _profile().search.permits
    assert recency_band(date(2026, 11, 1), TODAY, rules) == "d90"
    assert recency_band(date(2026, 7, 1), TODAY, rules) == "d180"
    assert recency_band(date(2026, 1, 1), TODAY, rules) == "d365"
    assert recency_band(date(2024, 1, 1), TODAY, rules) == "older"
    assert recency_band(None, TODAY, rules) == "none"


def test_search_sorts_by_score_then_recency(tmp_path):
    from leadgen.search import execute
    from leadgen.sources.records import SearchFilter

    outcome = execute(
        _profile(),
        SearchFilter(
            sources=["phoenix_permits", "tucson_permits"],
            permit_type="Building",
            date_from="2026-01-01",
        ),
        [],
        tmp_path,
        today=TODAY,
        network=False,
    )
    scores = [hit.score for hit in outcome.hits]
    assert scores == sorted(scores, reverse=True)


def test_summary_text_matches_hand_computed_numbers():
    counts = {"found": 120, "named": 34, "held": 0, "size": ""}
    assert _summary(counts, 50) == "120 businesses found \u00b7 34 with a named contact \u00b7 showing 50"
    assert _summary({"found": 1, "named": 0, "held": 2, "size": ""}, 1) == (
        "1 business found \u00b7 0 with a named contact \u00b7 showing 1 \u00b7 2 held back"
    )
    assert _summary({"found": 5, "named": 1, "held": 0, "size": "1\u201349: 2"}, 5).endswith(
        ". 1\u201349: 2"
    )


def test_size_breakdown_hidden_when_no_record_carries_a_size():
    from leadgen.industry import size_line
    from leadgen.sources.records import PublicRecord

    record = PublicRecord(source="sam", source_record_id="x", source_url="u", business_name="A")
    assert size_line([record], ["1-49"]) == ""
    sized = record.model_copy(update={"employee_count": 10})
    assert size_line([sized], ["1-49"]) != ""


def test_industry_cell_shows_the_permit_type_when_no_title():
    from leadgen.ui_data import _industry_cell

    record = _merged()["Desert Pipe Works Inc"]
    assert _industry_cell(record, "") == "From permit: Plumbing/Mechanical Work"
    assert _industry_cell(record, "722511") != "From permit: Plumbing/Mechanical Work"


def test_key_help_names_the_key_file_folder():
    from leadgen.sources.transport import plain_message

    sam = plain_message("sam", "sam_key")
    assert "Add SAM_API_KEY to your key file in C:\\Users\\msell\\secrets" in sam
    assert "LEADGEN_EDGAR_USER_AGENT" in plain_message("edgar", "edgar_agent")


def test_keys_in_the_key_file_are_read_at_search_time(tmp_path, monkeypatch):
    """A key added to the key file is used on the next search. A missing key says how to fix it."""
    from leadgen.search import execute
    from leadgen.sources.records import SearchFilter

    env = tmp_path / "keys.env"
    env.write_text("LEADGEN_LLM_MODE=live\n", encoding="utf-8")
    monkeypatch.setenv("LEADGEN_ENV_FILE", str(env))
    monkeypatch.delenv("LEADGEN_LLM_MODE", raising=False)
    monkeypatch.delenv("SAM_API_KEY", raising=False)
    seen = []

    def transport(url, params, headers, timeout):
        seen.append((url, dict(params)))
        return 200, '{"entityData": [], "totalRecords": 0}'

    filt = SearchFilter(sources=["sam"], state="AZ", cities=["Phoenix"])
    first = execute(_profile(), filt, [], tmp_path / "a", today=TODAY, transport=transport)
    assert any(
        r"Add SAM_API_KEY to your key file in C:\Users\msell\secrets" in line
        for line in first.statuses
    )
    assert seen == []

    env.write_text("LEADGEN_LLM_MODE=live\nSAM_API_KEY=test-key-123\n", encoding="utf-8")
    second = execute(_profile(), filt, [], tmp_path / "b", today=TODAY, transport=transport)
    assert seen and seen[0][1].get("api_key") == "test-key-123"
    assert not any("SAM_API_KEY" in line for line in second.statuses)


def test_permit_labels_read_plainly():
    from leadgen.permits import permit_label

    assert permit_label("Construction and Trades Commercial;Commercial;Commercial/Industrial;Tenant Improvement") == "Tenant Improvement"
    assert permit_label("Water/Sewer;Commercial;Commercial/Industrial;Water Services Shutdown") == "Water/Sewer: Water Services Shutdown"
    assert permit_label("Commercial Addition/Alteration Permit") == "Commercial Addition/Alteration Permit"


def test_a_customer_type_never_rescues_a_fire_alarm_or_a_sign():
    from leadgen.permits import relevance
    from leadgen.sources.records import PublicRecord

    rules = _profile().search.permits

    def row(permit_type, project, site):
        return PublicRecord(
            source="phoenix_permits", source_record_id="x", source_url="u",
            permit_type=permit_type, project=project, site_name=site,
        )

    assert relevance(row("Fire Alarm;Commercial;Commercial/Industrial;Installation", "ADDING SPRINKLER MONITOR", "SUNSET HILLS ASSISTED LIVING"), rules) == ""
    assert relevance(row("Sign Permit;Commercial;Commercial/Industrial;Ground", "Monument sign", "VALLEY MEDICAL CENTER"), rules) == ""
    assert relevance(row("Commercial Addition/Alteration Permit", "Lobby renovation", "Harbor Hotel"), rules) == "strong"
    assert relevance(row("Commercial Addition/Alteration Permit", "Lobby renovation", "Harbor Offices"), rules) == "some"
