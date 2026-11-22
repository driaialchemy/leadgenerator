"""Load a domain profile and the shared pipeline config."""

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from leadgen.paths import repo_root
from leadgen.phrases import is_banned
from leadgen.schemas import PipelineConfig, Profile

# Core fields a rule may name without declaring them as attributes.
# `range` is numeric. `in` is a category.
CORE_RANGE_FIELDS = frozenset({"last_engaged_days"})
CORE_IN_FIELDS = frozenset({"source", "consent_status", "region"})

_TOKEN = re.compile(r"\{\{([^{}]+)\}\}")
_ALLOWED_TOKENS = frozenset({"organization", "contact_first_name"})


def load_profile(profile_id: str, path: Path | None = None) -> Profile:
    """Read one profile YAML and check its rules, points, and subject tokens."""
    file = Path(path) if path is not None else _profile_path(profile_id)
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Profile file must be a mapping.")
    profile = _validate(Profile, data)
    if profile.profile_id != profile_id:
        raise ValueError(
            f"Profile id {profile.profile_id!r} does not match {profile_id!r}."
        )
    _check_points(profile)
    _check_rule_fields(profile)
    _check_subject_tokens(profile)
    _check_note_checks(profile)
    _check_approved_text(profile)
    return profile


def load_pipeline_config(path: Path | None = None) -> PipelineConfig:
    """Read pipeline.yaml. Stores the gates. Does not apply them."""
    file = Path(path) if path is not None else repo_root() / "config" / "pipeline.yaml"
    data = yaml.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Pipeline config must be a mapping.")
    return _validate(PipelineConfig, data)


def _profile_path(profile_id: str) -> Path:
    primary = repo_root() / "config" / "profiles" / f"{profile_id}.yaml"
    if primary.is_file():
        return primary
    return repo_root() / "tests" / "fixtures" / "profiles" / f"{profile_id}.yaml"


def _validate(model, data):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        message = exc.errors()[0]["msg"]
        raise ValueError(" ".join(message.splitlines())) from exc


def _check_points(profile: Profile) -> None:
    total = sum(rule.points for rule in profile.scoring_rules)
    if total != 100:
        raise ValueError(f"Scoring points sum to {total}, not 100.")


def _check_rule_fields(profile: Profile) -> None:
    for rule in profile.scoring_rules:
        declared = profile.attributes.get(rule.field)
        if rule.rule_type == "range":
            allowed = rule.field in CORE_RANGE_FIELDS or declared == "int"
        elif rule.rule_type == "grade":
            allowed = declared == "str"
        else:
            allowed = rule.field in CORE_IN_FIELDS or declared == "str"
        if not allowed:
            raise ValueError(
                f"Scoring rule field {rule.field!r} is not a core field "
                "or a declared attribute."
            )


def _check_note_checks(profile: Profile) -> None:
    seen: set[str] = set()
    for check in profile.note_checks:
        if check.id in seen:
            raise ValueError(f"Note check id {check.id!r} is repeated.")
        seen.add(check.id)
        for phrase in check.phrases:
            if not phrase.strip():
                raise ValueError(f"Note check {check.id!r} has an empty phrase.")
        if check.attribute is None:
            continue
        kind = profile.attributes.get(check.attribute)
        if kind is None:
            raise ValueError(
                f"Note check {check.id!r} names {check.attribute!r}, "
                "which is not a declared attribute."
            )
        if check.flag_when is not None and kind != "int":
            raise ValueError(
                f"Note check {check.id!r} uses flag_when on a non-int attribute."
            )


def _check_approved_text(profile: Profile) -> None:
    texts: list[tuple[str, str, str]] = [
        ("claim", claim_id, text) for claim_id, text in profile.approved_claims.items()
    ]
    texts += [
        ("subject", subject_id, text)
        for subject_id, text in profile.approved_subjects.items()
    ]
    texts.append(("cta", "cta", profile.cta))
    for kind, item_id, text in texts:
        for phrase in profile.banned_phrases:
            if is_banned(text, phrase):
                raise ValueError(
                    f"{kind} {item_id} contains the banned phrase {phrase!r}."
                )


def _check_subject_tokens(profile: Profile) -> None:
    for subject_id, text in profile.approved_subjects.items():
        bad = [token for token in _TOKEN.findall(text) if token not in _ALLOWED_TOKENS]
        if bad:
            raise ValueError(
                f"Subject {subject_id} uses {bad}. "
                "Only {{organization}} and {{contact_first_name}} are allowed."
            )
