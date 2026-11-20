"""Prompts stay inside each role's boundary."""

from pathlib import Path

from leadgen.loaders import load_prospects
from leadgen.messages import drafter_prompt, evaluator_prompt, tailor_prompt
from leadgen.paths import repo_root
from leadgen.profiles import load_profile
from leadgen.renderer import render
from leadgen.schemas import DraftEmail, TailorResult

ROOT = repo_root()


def test_prompt_files_have_no_email_address():
    for path in (ROOT / "prompts").glob("*.md"):
        assert "@" not in path.read_text(encoding="utf-8")


def test_evaluator_does_not_see_notes_or_the_tailor(tmp_path):
    profile = load_profile("b2b_services")
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == "B2B-001")
    tailor = TailorResult.model_validate_json(
        (ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-001" / "tailor.json").read_text(
            encoding="utf-8"
        )
    )
    draft = DraftEmail.model_validate_json(
        (
            ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-001" / "drafter.attempt2.json"
        ).read_text(encoding="utf-8")
    )
    rendered = render(draft, prospect, profile)
    text = evaluator_prompt(profile.buyer_persona, f"Subject: {rendered.subject}\n\n{rendered.body}\n")
    assert prospect.notes not in text
    for item in tailor.evidence:
        assert item.quote not in text
    assert "claim_ids" not in text
    assert tailor.model_dump_json() not in text
    template = (ROOT / "prompts" / "evaluator.md").read_text(encoding="utf-8")
    assert "claim_ids" not in template
    assert prospect.notes not in template


def test_tailor_prompt_omits_email_and_consent():
    profile = load_profile("b2b_services")
    prospect = next(item for item in load_prospects(profile) if item.prospect_id == "B2B-001")
    text = tailor_prompt(prospect, profile)
    assert prospect.email not in text
    assert "consent_status" not in text
    assert "do_not_contact" not in text
    drafter = drafter_prompt(
        prospect,
        profile,
        TailorResult.model_validate_json(
            (ROOT / "sample_data" / "replays" / "b2b_services" / "B2B-001" / "tailor.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert prospect.email not in drafter
