"""Exclusions run before anyone is scored."""

from leadgen.exclusions import apply_exclusions
from leadgen.loaders import load_prospects
from leadgen.profiles import load_pipeline_config, load_profile


def test_b2b_excludes_only_do_not_contact():
    profile = load_profile("b2b_services")
    eligible, excluded = apply_exclusions(load_prospects(profile), load_pipeline_config())
    assert [(item.prospect_id, item.reason) for item in excluded] == [
        ("B2B-005", "do_not_contact")
    ]
    assert "B2B-005" not in [prospect.prospect_id for prospect in eligible]


def test_home_excludes_only_no_consent():
    profile = load_profile("home_services")
    eligible, excluded = apply_exclusions(load_prospects(profile), load_pipeline_config())
    assert [(item.prospect_id, item.reason) for item in excluded] == [
        ("HOME-005", "no_consent")
    ]
    assert "HOME-005" not in [prospect.prospect_id for prospect in eligible]
