"""Industry match, Census size bands, and the Find step."""

import json
import urllib.parse
from pathlib import Path

from streamlit.testing.v1 import AppTest

from leadgen.industry import (
    BANDS,
    LIVE_SIZE_NOTE,
    PHOENIX_SKIPPED,
    band_for_census,
    keep_record,
    live_size_note,
    size_line,
    suggest,
)
from leadgen.paths import repo_root
from leadgen.profiles import load_profile
from leadgen.ui_data import profile_ids
from leadgen.search import search
from leadgen.sources.census_cbp import cbp_params, load_market, parse_cbp, sum_bands
from leadgen.sources.phoenix import phoenix_params
from leadgen.sources.records import SearchFilter, SourceQuery
from leadgen.sources.sam import parse_sam, sam_params

ROOT = repo_root()
APP = ROOT / "src" / "leadgen" / "app.py"
FIXTURE = ROOT / "sample_data" / "source_fixtures" / "census" / "cbp.json"


class _Count:
    def __init__(self, count):
        self.employee_count = count


def test_misspellings_match_official_titles():
    plumbing = suggest("plumbr")[:3]
    assert any("Plumbing" in match.title and "Contractor" in match.title for match in plumbing)
    assert suggest("dentst")[0].title == "Offices of Dentists"
    assert any("Restaurant" in match.title for match in suggest("resturant")[:3])
    assert any(match.title == "Landscaping Services" for match in suggest("landscaping companys")[:3])
    heating = suggest("hvac")[0]
    assert "Heating" in heating.title and "Air-Conditioning" in heating.title
    assert any("Account" in match.title for match in suggest("accountant")[:3])
    broader = suggest("zzzzqqqq")
    assert len(broader) == 3
    assert all(not match.confident for match in broader)
    assert all(not match.code.isdigit() or len(match.code) <= 2 for match in broader)


def test_size_bands_keep_unknown_records_and_match_the_summary():
    records = [
        _Count(10),
        _Count(49),
        _Count(50),
        _Count(249),
        _Count(250),
        _Count(500),
        _Count(999),
        _Count(1000),
        _Count(None),
    ]
    bands = [band.id for band in BANDS]
    assert size_line(records, bands) == "1–49: 2, 50–249: 2, 250–499: 1, 500–999: 2"
    assert keep_record(_Count(None), ["1-49"], False) is True
    assert keep_record(_Count(None), ["1-49"], True) is False
    assert keep_record(_Count(10), ["50-249"], False) is False
    assert keep_record(_Count(1000), bands, False) is False
    assert keep_record(_Count(12), [], False) is True


def test_census_fixture_sums_the_four_bands_and_ignores_other_classes():
    rows = parse_cbp(FIXTURE.read_text(encoding="utf-8"))
    totals = sum_bands(rows, "621210", "04", "013")
    assert band_for_census("212") == band_for_census("220") == "1-49"
    assert band_for_census("230") == band_for_census("241") == "1-49"
    assert band_for_census("242") == band_for_census("251") == "50-249"
    assert band_for_census("252") == "250-499"
    assert band_for_census("254") == "500-999"
    assert band_for_census("001") == ""
    assert band_for_census("260") == ""
    # 10+20+30+40, 5+7, 3, 2. The 999 all-sizes row, the 8 of 1000+, and another county's 1000 stay out.
    assert totals == {"1-49": 100, "50-249": 12, "250-499": 3, "500-999": 2}


def test_census_params_use_the_fixed_template_only():
    params = cbp_params("621210", "04", "013", "212")
    blob = urllib.parse.urlencode(params)
    assert blob == (
        "get=ESTAB%2CNAICS2017%2CEMPSZES&for=county%3A013&in=state%3A04"
        "&NAICS2017=621210&EMPSZES=212&LFO=001"
    )
    assert "plumbr" not in blob
    for value in ("plumbr", "Maricopa", "AZ"):
        try:
            cbp_params(value, "04", "013", "212")
        except ValueError:
            refused = True
        else:
            refused = False
        assert refused


def test_census_failure_is_plain_and_the_search_still_returns(tmp_path, monkeypatch):
    def broken():
        raise ValueError("secret token in the body")

    monkeypatch.setattr("leadgen.sources.census_cbp._fixture", broken)
    outcome = search(load_profile("b2b_services"), "Registered firms in Phoenix", tmp_path)
    assert outcome.shown == 3
    assert outcome.messages == [
        "County Business Patterns did not respond. The business search is unchanged."
    ]
    assert "secret" not in " ".join(outcome.messages)
    assert all(hit.record.employee_count is None for hit in outcome.hits)


def test_census_cache_leaves_the_key_out(tmp_path, monkeypatch):
    secret = "CENSUSSECRETVALUE"
    monkeypatch.setenv("CENSUS_API_KEY", secret)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def transport(url, params, headers, timeout):
        asked = dict(params)
        assert asked["key"] == secret
        assert "plumbr" not in urllib.parse.urlencode(params)
        header, *data = fixture
        kept = [
            row
            for row in data
            if row[1] == asked["NAICS2017"] and row[2] == asked["EMPSZES"]
        ]
        return 200, json.dumps([header, *kept])

    county = load_profile("b2b_services").search.county
    market, message = load_market(county, ["621210"], ["1-49"], tmp_path, 24, True, transport)
    assert message == ""
    assert market["year"] == "2023"
    assert market["industries"][0]["bands"][0]["count"] == 100
    assert "not a list of businesses" in market["note"]
    files = list((tmp_path / "runs" / "source_cache").rglob("*.json"))
    assert files
    blob = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert secret not in blob


def test_chosen_codes_never_send_the_typed_words(tmp_path):
    profile = load_profile("b2b_services")
    outcome = search(
        profile,
        "plumbr",
        tmp_path,
        chosen_naics=["238220"],
        chosen_sizes=["1-49"],
    )
    params = sam_params(
        SourceQuery(
            naics=outcome.filter.naics,
            state=outcome.filter.state,
            city=outcome.filter.city,
            business_type=outcome.filter.business_type,
        ),
        10,
    )
    blob = urllib.parse.urlencode(params)
    assert "238220" in blob
    assert "plumbr" not in blob
    log = (tmp_path / "runs" / "flight_recorder.jsonl").read_text(encoding="utf-8")
    assert "plumbr" in log
    assert "238220" in log
    assert "1-49" in log
    home = load_profile("home_services")
    mapped = search(home, "plumbr", tmp_path, chosen_naics=["238220"])
    permit = urllib.parse.urlencode(phoenix_params(SourceQuery(permit_type=mapped.filter.permit_type), 10))
    assert mapped.filter.permit_type == "Building"
    assert "plumbr" not in permit
    skipped = search(home, "dentist office", tmp_path, chosen_naics=["621210"])
    assert "phoenix_permits" not in skipped.filter.sources
    assert PHOENIX_SKIPPED in skipped.messages


def test_translator_can_fill_an_official_code_and_a_size_band(tmp_path):
    replay = tmp_path / "sample_data" / "replays" / "b2b_services" / "search"
    replay.mkdir(parents=True)
    (replay / "translator.json").write_text(
        json.dumps(
            {
                "sources": ["sam", "edgar"],
                "naics": ["621210"],
                "state": "AZ",
                "city": "Phoenix",
                "business_type": "For Profit Organization",
                "permit_type": "",
                "date_from": "",
                "date_to": "",
                "area": "",
                "sizes": ["1-49"],
                "unsupported": [],
            }
        ),
        encoding="utf-8",
    )
    outcome = search(load_profile("b2b_services"), "small dental offices in Phoenix", tmp_path)
    assert outcome.filter.naics == ["621210"]
    assert outcome.filter.sizes == ["1-49"]
    assert "1–49: 100" in outcome.market["industries"][0]["bands"][0]["label"] + ": " + str(
        outcome.market["industries"][0]["bands"][0]["count"]
    )


def test_sam_does_not_copy_a_headcount():
    raw = json.loads((ROOT / "sample_data" / "source_fixtures" / "sam" / "entities.json").read_text(encoding="utf-8"))
    raw["entityData"][0]["coreData"]["sizeMetrics"] = {
        "averageNumberOfEmployees": 40,
        "averageAnnualRevenue": 900000,
    }
    record = parse_sam(json.dumps(raw))[0]
    assert record.employee_count is None
    assert "40" not in json.dumps(record.model_dump(mode="json"))


def test_live_mode_names_the_market_card_as_the_size_view():
    assert live_size_note("offline") == ""
    assert live_size_note("live") == LIVE_SIZE_NOTE
    assert "headcount" in LIVE_SIZE_NOTE


def test_every_profile_can_pick_an_industry_and_a_size(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    assert list(at.exception) == []
    assert _primaries(at) == ["Search"]
    for profile_id in profile_ids():
        at.selectbox(key="profile").set_value(profile_id).run(timeout=60)
        at.text_input(key="industry_query").set_value("plumbr").run(timeout=60)
        assert at.text_input(key="industry_query").value == "plumbr"
        assert "Did you mean" in _text(at)
        assert _primaries(at) == ["Search"]
        at.button(key="suggest_0").click().run(timeout=60)
        at.multiselect(key="size_bands").set_value(["1–49"]).run(timeout=60)
        at.button(key="search").click().run(timeout=60)
        assert list(at.exception) == []
        assert at.multiselect(key="size_bands").value == ["1–49"]
        assert "238220" in _text(at)
        assert _primaries(at) == ["Next"]
    at.run(timeout=60)
    assert at.text_input(key="industry_query").value == "plumbr"
    at.button(key="nav_shortlist").click().run(timeout=60)
    at.button(key="nav_search").click().run(timeout=60)
    assert at.text_input(key="industry_query").value == "plumbr"
    assert at.multiselect(key="size_bands").value == ["1–49"]


def test_removing_a_chip_changes_the_next_search(monkeypatch, tmp_path):
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    at.text_input(key="industry_query").set_value("plumbr").run(timeout=60)
    at.button(key="suggest_0").click().run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    assert list(at.exception) == []
    assert "238220" in _text(at)
    at.button(key="chip_238220").click().run(timeout=60)
    at.text_input(key="search_query").set_value("Registered firms in Phoenix").run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    assert list(at.exception) == []
    assert "541512" in _text(at)


def test_a_filled_size_survives_on_the_page(monkeypatch, tmp_path):
    replay = tmp_path / "sample_data" / "replays" / "b2b_services" / "search"
    replay.mkdir(parents=True)
    (replay / "translator.json").write_text(
        json.dumps(
            {
                "sources": ["sam", "edgar"],
                "naics": ["621210"],
                "state": "AZ",
                "city": "Phoenix",
                "business_type": "For Profit Organization",
                "permit_type": "",
                "date_from": "",
                "date_to": "",
                "area": "",
                "sizes": ["1-49"],
                "unsupported": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LEADGEN_DATA_ROOT", str(tmp_path))
    at = AppTest.from_file(str(APP))
    at.run(timeout=60)
    at.text_input(key="search_query").set_value("small dental offices in Phoenix").run(timeout=60)
    at.button(key="search").click().run(timeout=60)
    assert list(at.exception) == []
    text = _text(at)
    assert "Offices of Dentists" in text
    assert "County totals" in text
    assert "not a list of businesses" in text
    assert "2023" in text
    assert at.multiselect(key="size_bands").value == ["1–49"]
    assert at.button(key="chip_621210").label == "Offices of Dentists"


def _primaries(at) -> list[str]:
    return [button.label for button in at.button if button.proto.type == "primary"]


def _text(at) -> str:
    chunks = []
    for name in ("markdown", "header", "info", "warning", "caption", "text", "subheader"):
        block = getattr(at, name, None)
        if not block:
            continue
        for item in block:
            value = getattr(item, "value", None) or getattr(item, "label", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)
