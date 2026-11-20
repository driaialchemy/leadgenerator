"""Read prospect and outcome CSV files for one profile."""

import csv
import re
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from leadgen.paths import repo_root
from leadgen.schemas import Outcome, Profile, Prospect

PROSPECT_COLUMNS = (
    "prospect_id",
    "profile_id",
    "contact_name",
    "organization",
    "email",
    "region",
    "source",
    "last_engaged_days",
    "consent_status",
    "do_not_contact",
    "notes",
)

OUTCOME_COLUMNS = (
    "record_id",
    "profile_id",
    "sent_on",
    "furthest_stage",
    "deal_value",
)


def load_prospects(profile: Profile, path: Path | None = None) -> list[Prospect]:
    """Read prospects.csv. Extra columns and missing attributes are rejected."""
    file = Path(path) if path is not None else _sample_path(profile, "prospects.csv")
    rows = _read_rows(file, PROSPECT_COLUMNS, profile)
    prospects: list[Prospect] = []
    for row in rows:
        if row["profile_id"].strip() != profile.profile_id:
            raise ValueError(
                f"Prospect {row['prospect_id'].strip()!r} is not in this profile."
            )
        organization = row["organization"].strip()
        try:
            prospects.append(
                Prospect(
                    prospect_id=row["prospect_id"].strip(),
                    profile_id=row["profile_id"].strip(),
                    contact_name=row["contact_name"].strip(),
                    organization=organization or None,
                    email=row["email"].strip(),
                    region=row["region"].strip(),
                    source=row["source"].strip(),
                    last_engaged_days=_whole_number(row["last_engaged_days"], "last_engaged_days"),
                    consent_status=row["consent_status"].strip(),
                    do_not_contact=_parse_bool(row["do_not_contact"]),
                    notes=row["notes"].strip(),
                    attributes=_attributes(row, profile),
                )
            )
        except ValidationError as exc:
            raise ValueError(_validation_message(exc)) from exc
    return prospects


def load_outcomes(profile: Profile, path: Path | None = None) -> list[Outcome]:
    """Read outcomes.csv. A blank deal_value becomes null."""
    file = Path(path) if path is not None else _sample_path(profile, "outcomes.csv")
    rows = _read_rows(file, OUTCOME_COLUMNS, None)
    outcomes: list[Outcome] = []
    for row in rows:
        if row["profile_id"].strip() != profile.profile_id:
            raise ValueError(
                f"Outcome {row['record_id'].strip()!r} is not in this profile."
            )
        try:
            outcomes.append(
                Outcome(
                    record_id=row["record_id"].strip(),
                    profile_id=row["profile_id"].strip(),
                    sent_on=_parse_date(row["sent_on"]),
                    furthest_stage=row["furthest_stage"].strip(),
                    deal_value=_deal_value(row["deal_value"]),
                )
            )
        except ValidationError as exc:
            raise ValueError(_validation_message(exc)) from exc
    return outcomes


def _sample_path(profile: Profile, name: str) -> Path:
    return repo_root() / "sample_data" / profile.profile_id / name


def _read_rows(path: Path, required: tuple[str, ...], profile: Profile | None) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        _check_headers(fieldnames, required, profile)
        rows = []
        for row in reader:
            if row is None:
                continue
            if all(not (value or "").strip() for value in row.values()):
                continue
            rows.append({key: (value if value is not None else "") for key, value in row.items()})
        return rows


def _check_headers(fieldnames: list[str], required: tuple[str, ...], profile: Profile | None) -> None:
    missing = [name for name in required if name not in fieldnames]
    if missing:
        raise ValueError(f"CSV is missing columns: {', '.join(missing)}.")
    if profile is None:
        extras = [name for name in fieldnames if name not in required]
        if extras:
            raise ValueError(f"Column {extras[0]!r} is not an outcome column.")
        return
    declared = set(profile.attributes)
    extras = [name for name in fieldnames if name not in required and name not in declared]
    if extras:
        raise ValueError(f"Column {extras[0]!r} is not a declared attribute.")
    missing_attrs = [name for name in profile.attributes if name not in fieldnames]
    if missing_attrs:
        raise ValueError(
            f"Prospect CSV is missing attribute columns: {', '.join(missing_attrs)}."
        )


def _attributes(row: dict[str, str], profile: Profile) -> dict[str, int | str]:
    parsed: dict[str, int | str] = {}
    for name, kind in profile.attributes.items():
        text = row[name].strip()
        if kind == "int":
            parsed[name] = _whole_number(text, name, signed=True)
        else:
            parsed[name] = text
    return parsed


def _whole_number(value: str, label: str, signed: bool = False) -> int:
    text = value.strip()
    pattern = r"-?\d+" if signed else r"\d+"
    if not re.fullmatch(pattern, text):
        raise ValueError(f"{label} must be a whole number, got {text!r}.")
    return int(text)


def _parse_bool(value: str) -> bool:
    text = value.strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"do_not_contact must be true or false, got {value!r}.")


def _parse_date(value: str) -> date:
    text = value.strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"sent_on must be YYYY-MM-DD, got {text!r}.") from exc


def _deal_value(value: str) -> int | None:
    text = value.strip()
    if text == "":
        return None
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"deal_value must be a whole number or blank, got {text!r}.")
    return int(text)


def _validation_message(exc: ValidationError) -> str:
    return " ".join(exc.errors()[0]["msg"].splitlines())
