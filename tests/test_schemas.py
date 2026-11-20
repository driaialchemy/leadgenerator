"""Schema rules for prospects and outcomes."""

from datetime import date

import pytest
from pydantic import ValidationError

from leadgen.schemas import Outcome, Prospect


def _prospect_data():
    return {
        "prospect_id": "P-1",
        "profile_id": "sample",
        "contact_name": "Ada Lovelace",
        "organization": "Example Co",
        "email": "ada@example.com",
        "region": "Phoenix",
        "source": "referral",
        "last_engaged_days": 3,
        "consent_status": "opt_in",
        "do_not_contact": False,
        "notes": "Asked for a short call.",
        "attributes": {"employee_count": 10},
    }


def test_valid_prospect_loads():
    prospect = Prospect(**_prospect_data())
    assert prospect.prospect_id == "P-1"
    assert prospect.last_engaged_days == 3
    assert prospect.attributes["employee_count"] == 10


def test_unknown_field_is_rejected():
    data = _prospect_data()
    data["nickname"] = "Dee"
    with pytest.raises(ValidationError):
        Prospect.model_validate(data)


def test_invalid_consent_status_is_rejected():
    data = _prospect_data()
    data["consent_status"] = "maybe"
    with pytest.raises(ValidationError):
        Prospect.model_validate(data)


def test_negative_last_engaged_days_is_rejected():
    data = _prospect_data()
    data["last_engaged_days"] = -1
    with pytest.raises(ValidationError):
        Prospect.model_validate(data)


def test_won_without_deal_value_is_rejected():
    with pytest.raises(ValidationError):
        Outcome(
            record_id="OUT-1",
            profile_id="sample",
            sent_on=date(2026, 1, 15),
            furthest_stage="won",
        )


def test_non_won_with_deal_value_is_rejected():
    with pytest.raises(ValidationError):
        Outcome(
            record_id="OUT-1",
            profile_id="sample",
            sent_on=date(2026, 1, 15),
            furthest_stage="sent",
            deal_value=18000,
        )
