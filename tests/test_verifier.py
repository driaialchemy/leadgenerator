"""The verifier blocks AI-written text and still reports findings."""

import json
from pathlib import Path

import pytest

from leadgen.loaders import load_prospects
from leadgen.profiles import load_pipeline_config, load_profile
from leadgen.schemas import DraftEmail, EvidenceQuote, TailorResult
from leadgen.verifier import IneligibleProspect, verify

ROOT = Path(__file__).resolve().parents[1]


def test_good_drafts_pass():
    for name, profile_id, prospect_id in (
        ("b2b_001_good.json", "b2b_services", "B2B-001"),
        ("home_002_good.json", "home_services", "HOME-002"),
    ):
        report = _verify(name, profile_id, prospect_id)
        assert report.passed is True
        assert report.blocking == []


def test_b2b_caught_draft():
    report = _verify("b2b_001_caught.json", "b2b_services", "B2B-001")
    assert report.passed is False
    assert {issue.code for issue in report.blocking} == {
        "raw_fact",
        "digits",
        "banned_phrase",
    }
    assert "pricing_question" in [item.check_id for item in report.findings]
    assert _message_has(report, "raw_fact", "Mesa Ridge Dental")
    assert _message_has(report, "digits", "20")
    assert _message_has(report, "banned_phrase", "% off")
    _every_message_names_text(report)


def test_home_caught_draft():
    report = _verify("home_002_caught.json", "home_services", "HOME-002")
    assert report.passed is False
    assert {issue.code for issue in report.blocking} == {"digits", "banned_phrase"}
    assert _message_has(report, "digits", "1,500")
    assert _message_has(report, "banned_phrase", "$")
    _every_message_names_text(report)


def test_empty_organization_token():
    report = _verify(
        "home_002_good.json",
        "home_services",
        "HOME-002",
        draft_update={"hook": "A note for {{organization}} today."},
    )
    assert {issue.code for issue in report.blocking} == {"empty_token"}
    assert _message_has(report, "empty_token", "{{organization}}")


def test_unknown_token():
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        draft_update={"hook": "Asking about {{price}} today."},
    )
    assert {issue.code for issue in report.blocking} == {"unknown_token"}
    assert _message_has(report, "unknown_token", "{{price}}")


def test_unknown_claim():
    quote = EvidenceQuote(claim_id="VP-B2B-99", quote="Backups 'probably' run")
    kept = EvidenceQuote(
        claim_id="VP-B2B-04", quote="Sister practice had a ransomware scare"
    )
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        tailor_update={
            "claim_ids": ["VP-B2B-99", "VP-B2B-04"],
            "evidence": [quote, kept],
        },
        draft_update={"claim_ids": ["VP-B2B-99", "VP-B2B-04"]},
    )
    assert {issue.code for issue in report.blocking} == {"unknown_claim"}
    assert _message_has(report, "unknown_claim", "VP-B2B-99")


def test_three_claims_fail_count():
    third = EvidenceQuote(claim_id="VP-B2B-01", quote="Office mgr Dana")
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        tailor_update={"claim_ids": ["VP-B2B-02", "VP-B2B-04", "VP-B2B-01"]},
        draft_update={"claim_ids": ["VP-B2B-02", "VP-B2B-04", "VP-B2B-01"]},
        extra_evidence=[third],
    )
    assert {issue.code for issue in report.blocking} == {"claim_count"}
    assert _message_has(report, "claim_count", "3")


def test_duplicate_claim_ids_fail_count():
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        tailor_update={"claim_ids": ["VP-B2B-02", "VP-B2B-02"]},
        draft_update={"claim_ids": ["VP-B2B-02", "VP-B2B-02"]},
    )
    assert {issue.code for issue in report.blocking} == {"claim_count"}
    assert _message_has(report, "claim_count", "VP-B2B-02")


def test_swapped_claim_order_passes():
    _tailor, draft = _load("b2b_001_good.json")
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        draft_update={"claim_ids": list(reversed(draft.claim_ids))},
    )
    assert report.passed is True
    assert report.blocking == []


def test_quote_not_in_notes():
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        replace_quote=("VP-B2B-02", "purple widgets"),
    )
    assert {issue.code for issue in report.blocking} == {"evidence_not_in_notes"}
    assert _message_has(report, "evidence_not_in_notes", "purple widgets")


def test_one_word_quote():
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        replace_quote=("VP-B2B-02", "Backups"),
    )
    assert {issue.code for issue in report.blocking} == {"evidence_not_in_notes"}
    assert _message_has(report, "evidence_not_in_notes", "Backups")


def test_claim_sets_must_match():
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        draft_update={"claim_ids": ["VP-B2B-02"]},
    )
    assert {issue.code for issue in report.blocking} == {"claim_mismatch"}
    assert _message_has(report, "claim_mismatch", "VP-B2B-04")


def test_hook_over_the_word_cap():
    _tailor, draft = _load("b2b_001_good.json")
    hook = " ".join(["alpha"] * 91)
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        draft_update={"hook": hook},
    )
    assert {issue.code for issue in report.blocking} == {"too_long"}
    total = 91 + len(draft.bridge.split())
    assert _message_has(report, "too_long", str(total))


def test_freedom_is_not_the_banned_word_free():
    _tailor, draft = _load("b2b_001_good.json")
    report = _verify(
        "b2b_001_good.json",
        "b2b_services",
        "B2B-001",
        draft_update={"hook": draft.hook + " freedom"},
    )
    assert report.passed is True
    assert report.blocking == []


def test_below_threshold_is_ineligible():
    with pytest.raises(IneligibleProspect, match="B2B-003"):
        _verify("b2b_001_good.json", "b2b_services", "B2B-003")


def test_excluded_prospect_is_ineligible():
    with pytest.raises(IneligibleProspect, match="B2B-005"):
        _verify("b2b_001_good.json", "b2b_services", "B2B-005")


def _verify(
    name,
    profile_id,
    prospect_id,
    draft_update=None,
    tailor_update=None,
    extra_evidence=None,
    replace_quote=None,
):
    tailor, draft = _load(name)
    if replace_quote:
        claim_id, quote = replace_quote
        evidence = []
        for item in tailor.evidence:
            if item.claim_id == claim_id:
                evidence.append(item.model_copy(update={"quote": quote}))
            else:
                evidence.append(item)
        tailor = tailor.model_copy(update={"evidence": evidence})
    if extra_evidence:
        tailor = tailor.model_copy(
            update={"evidence": [*tailor.evidence, *extra_evidence]}
        )
    if tailor_update:
        tailor = tailor.model_copy(update=tailor_update)
    if draft_update:
        draft = draft.model_copy(update=draft_update)
    profile = load_profile(profile_id)
    prospect = next(
        item for item in load_prospects(profile) if item.prospect_id == prospect_id
    )
    return verify(tailor, draft, prospect, profile, load_pipeline_config())


def _load(name):
    data = json.loads(
        (ROOT / "tests" / "fixtures" / "drafts" / name).read_text(encoding="utf-8")
    )
    return (
        TailorResult.model_validate(data["tailor"]),
        DraftEmail.model_validate(data["draft"]),
    )


def _message_has(report, code, text):
    return any(text in issue.message for issue in report.blocking if issue.code == code)


def _every_message_names_text(report):
    for issue in report.blocking:
        assert "'" in issue.message
