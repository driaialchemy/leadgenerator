"""Score a prospect from the profile rules. Every point names its rule."""

from leadgen.exclusions import apply_exclusions
from leadgen.schemas import (
    Excluded,
    PipelineConfig,
    Profile,
    Prospect,
    RuleHit,
    ScoreResult,
    ScoringRule,
)


def score(prospect: Prospect, profile: Profile, pipeline: PipelineConfig) -> ScoreResult:
    """Score one prospect. This does not apply exclusions."""
    hits: list[RuleHit] = []
    total = 0
    for rule in profile.scoring_rules:
        matched = _matches(rule, _field_value(prospect, rule.field))
        hits.append(RuleHit(field=rule.field, points=rule.points, matched=matched))
        if matched:
            total += rule.points
    return ScoreResult(
        prospect_id=prospect.prospect_id,
        total=total,
        tier=_tier(total, pipeline),
        draft_eligible=total >= pipeline.draft_threshold,
        rule_hits=hits,
    )


def qualify(
    prospects: list[Prospect], profile: Profile, pipeline: PipelineConfig
) -> tuple[list[ScoreResult], list[Excluded]]:
    """Exclusions first, then score the rest. Highest score, then prospect id."""
    eligible, excluded = apply_exclusions(prospects, pipeline)
    ranked = [score(prospect, profile, pipeline) for prospect in eligible]
    ranked.sort(key=lambda result: (-result.total, result.prospect_id))
    return ranked, excluded


def _field_value(prospect: Prospect, field: str):
    core = {
        "last_engaged_days": prospect.last_engaged_days,
        "source": prospect.source,
        "consent_status": prospect.consent_status,
        "region": prospect.region,
    }
    if field in core:
        return core[field]
    return prospect.attributes.get(field)


def _matches(rule: ScoringRule, value) -> bool:
    if rule.rule_type == "range":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        if rule.min is not None and value < rule.min:
            return False
        if rule.max is not None and value > rule.max:
            return False
        return True
    if value is None:
        return False
    return value in (rule.values or [])


def _tier(total: int, pipeline: PipelineConfig) -> str:
    if total >= pipeline.tiers.hot_min:
        return "hot"
    if total >= pipeline.tiers.warm_min:
        return "warm"
    return "cold"
