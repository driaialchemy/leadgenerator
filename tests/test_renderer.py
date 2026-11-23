"""Code fills tokens, claims, and the footer."""

import json
from pathlib import Path

from leadgen.loaders import load_prospects
from leadgen.profiles import load_profile
from leadgen.renderer import render
from leadgen.schemas import DraftEmail, TailorResult

ROOT = Path(__file__).resolve().parents[1]


def test_b2b_good_draft_renders():
    _tailor, draft = _fixture("b2b_001_good.json")
    profile = load_profile("b2b_services")
    prospect = _prospect(profile, "B2B-001")
    rendered = render(draft, prospect, profile)
    assert rendered.subject == "Backups and security for Mesa Ridge Dental"
    body = rendered.body
    assert body.startswith("Hi Dana,")
    assert "Mesa Ridge Dental" in body
    # Approved claims are checked by the verifier and no longer printed as bullets.
    assert "Daily backups with quarterly restore tests" not in body
    assert "\n- " not in body
    assert profile.cta in body
    assert profile.sender.name in body
    assert profile.sender.postal_address in body
    assert profile.opt_out_line in body
    assert "{{" not in body


def test_closing_block_order():
    _tailor, draft = _fixture("b2b_001_good.json")
    profile = load_profile("b2b_services")
    prospect = _prospect(profile, "B2B-001")
    body = render(draft, prospect, profile).body
    order = [body.index(text) for text in (profile.cta, "Best,", profile.sender.name, profile.sender.postal_address, profile.opt_out_line)]
    assert order == sorted(order)


def _fixture(name):
    data = json.loads((ROOT / "tests" / "fixtures" / "drafts" / name).read_text(encoding="utf-8"))
    return TailorResult.model_validate(data["tailor"]), DraftEmail.model_validate(data["draft"])


def _prospect(profile, prospect_id):
    return next(item for item in load_prospects(profile) if item.prospect_id == prospect_id)
