"""Re-read the tailor file and check claims and evidence.

The verifier module is not edited. These helpers already know the rules.
"""

from leadgen.schemas import (
    BlockingIssue,
    DraftEmail,
    PipelineConfig,
    Profile,
    Prospect,
    TailorResult,
)
from leadgen.verifier import (
    _claim_count,
    _evidence_quotes,
    _missing_evidence,
    _unknown_claims,
)


def check_tailor(
    tailor: TailorResult, prospect: Prospect, profile: Profile, pipeline: PipelineConfig
) -> list[BlockingIssue]:
    """Claim ids, duplicates, and evidence quotes. Hook text is not judged here."""
    stand_in = DraftEmail(
        prospect_id=tailor.prospect_id,
        subject_id=next(iter(profile.approved_subjects)),
        claim_ids=list(tailor.claim_ids),
        hook="Placeholder for the claim gate only.",
        bridge="Placeholder for the claim gate only.",
    )
    issues: list[BlockingIssue] = []
    issues += _unknown_claims(tailor, stand_in, profile)
    issues += _claim_count(tailor, stand_in, pipeline)
    issues += _missing_evidence(tailor, stand_in)
    issues += _evidence_quotes(tailor, prospect)
    return issues
