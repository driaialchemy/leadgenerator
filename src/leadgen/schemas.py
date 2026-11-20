"""Prospect, profile, pipeline, and outcome shapes. Unknown fields are rejected."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Source = Literal["referral", "web_form", "event", "cold_list"]
ConsentStatus = Literal["opt_in", "existing_relationship", "none"]
Stage = Literal["sent", "replied", "meeting", "won", "lost_after_meeting"]
AttributeType = Literal["int", "str"]
RuleType = Literal["range", "in"]


class Prospect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospect_id: str
    profile_id: str
    contact_name: str
    organization: str | None = None
    email: str
    region: str
    source: Source
    last_engaged_days: int = Field(ge=0)
    consent_status: ConsentStatus
    do_not_contact: bool
    notes: str
    attributes: dict[str, int | str]


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    profile_id: str
    sent_on: date
    furthest_stage: Stage
    deal_value: int | None = None

    @model_validator(mode="after")
    def deal_value_matches_stage(self) -> "Outcome":
        if self.furthest_stage == "won":
            if self.deal_value is None or self.deal_value <= 0:
                raise ValueError("A won outcome needs a deal_value greater than 0.")
        elif self.deal_value is not None:
            raise ValueError("deal_value is only allowed when furthest_stage is won.")
        return self


class Sender(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    company: str
    postal_address: str


class ScoringRule(BaseModel):
    """A scoring rule. YAML keys are `type`, `min`, and `max`."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    field: str
    rule_type: RuleType = Field(alias="type")
    min: int | None = None
    max: int | None = None
    values: list[str] | None = None
    points: int = Field(ge=0)

    @model_validator(mode="after")
    def shape_matches_type(self) -> "ScoringRule":
        if self.rule_type == "range":
            if self.values is not None:
                raise ValueError("A range rule does not take a values list.")
            if self.min is None and self.max is None:
                raise ValueError("A range rule needs a min, a max, or both.")
            if self.min is not None and self.max is not None and self.min > self.max:
                raise ValueError("A range rule min cannot be greater than its max.")
        else:
            if self.min is not None or self.max is not None:
                raise ValueError("An 'in' rule does not take min or max.")
            if not self.values:
                raise ValueError("An 'in' rule needs a values list.")
        return self


class FlagWhen(BaseModel):
    """Inclusive bounds for a note check. At least one side is required."""

    model_config = ConfigDict(extra="forbid")

    min: int | None = None
    max: int | None = None

    @model_validator(mode="after")
    def bounds(self) -> "FlagWhen":
        if self.min is None and self.max is None:
            raise ValueError("flag_when needs a min, a max, or both.")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("flag_when min cannot be greater than its max.")
        return self


class NoteCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    phrases: list[str]
    attribute: str | None = None
    flag_when: FlagWhen | None = None
    message: str

    @model_validator(mode="after")
    def shape(self) -> "NoteCheck":
        if self.flag_when is not None and not self.attribute:
            raise ValueError("flag_when needs an attribute.")
        if not self.phrases:
            raise ValueError("A note check needs at least one phrase.")
        if not self.message.strip():
            raise ValueError("A note check needs a message.")
        return self


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    sender: Sender
    opt_out_line: str
    attributes: dict[str, AttributeType]
    scoring_rules: list[ScoringRule]
    approved_claims: dict[str, str]
    approved_subjects: dict[str, str]
    cta: str
    note_checks: list[NoteCheck]
    banned_phrases: list[str]
    buyer_persona: str


class TierBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hot_min: int
    warm_min: int

    @model_validator(mode="after")
    def check_bounds(self) -> "TierBounds":
        if not (0 <= self.warm_min < self.hot_min <= 100):
            raise ValueError("Tier bounds must satisfy 0 <= warm_min < hot_min <= 100.")
        return self


class Exclusions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    do_not_contact_is: bool
    consent_status_is: list[str]


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_threshold: int
    tiers: TierBounds
    max_revisions: int = Field(ge=0)
    evaluator_pass_score: int = Field(ge=1, le=5)
    max_ai_words: int = Field(ge=10)
    max_claims: int = Field(ge=1)
    exclusions: Exclusions

    @model_validator(mode="after")
    def check_draft_threshold(self) -> "PipelineConfig":
        if not (0 <= self.draft_threshold <= 100):
            raise ValueError("draft_threshold must satisfy 0 <= draft_threshold <= 100.")
        return self


TierName = Literal["hot", "warm", "cold"]
ExclusionReason = Literal["do_not_contact", "no_consent"]
BlockingCode = Literal[
    "unknown_token",
    "empty_token",
    "raw_fact",
    "digits",
    "banned_phrase",
    "unknown_subject",
    "unknown_claim",
    "claim_count",
    "claim_mismatch",
    "missing_evidence",
    "evidence_not_in_notes",
    "too_long",
    "empty_text",
]


class Excluded(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospect_id: str
    reason: ExclusionReason


class RuleHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    points: int
    matched: bool


class ScoreResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospect_id: str
    total: int
    tier: TierName
    draft_eligible: bool
    rule_hits: list[RuleHit]


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    prospect_id: str
    message: str


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    quote: str


class TailorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospect_id: str
    claim_ids: list[str]
    evidence: list[EvidenceQuote]


class DraftEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prospect_id: str
    subject_id: str
    claim_ids: list[str]
    hook: str
    bridge: str


class RenderedEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str


class BlockingIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: BlockingCode
    field: str
    message: str


class VerifyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    blocking: list[BlockingIssue]
    findings: list[Finding]


class Funnel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sent: int
    replied: int
    meeting: int
    won: int
    won_value: int
    reply_rate: float
    meeting_rate: float
    win_rate: float
    avg_deal: float


class EvaluatorResult(BaseModel):
    """Scores from the blind reader. Code decides pass or fail."""

    model_config = ConfigDict(extra="forbid")

    relevance: int = Field(ge=1, le=5)
    specificity: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    tone: int = Field(ge=1, le=5)
    suggestions: list[str] = Field(min_length=1, max_length=3)


EventType = Literal[
    "model_call",
    "gate",
    "verifier",
    "evaluator",
    "retry",
    "approval",
    "outbox",
    "refusal",
    "kill_switch_block",
    "error",
]


class FlightEvent(BaseModel):
    """One line in the append-only flight recorder."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    ts: str
    run_id: str
    event_type: EventType
    actor: str
    mode: Literal["offline", "live"]
    model: str | None = None
    provider: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    red_team: bool = False
    attempt_number: int | None = None
    retry_of: str | None = None
    retry_reason: str | None = None
    input_sha256: str | None = None
    output_path: str | None = None
    status: Literal["ok", "fail", "blocked"]
    detail: str


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVED", "EDITED", "REJECTED"]
    name: str
    ack_findings: bool
    run_id: str
