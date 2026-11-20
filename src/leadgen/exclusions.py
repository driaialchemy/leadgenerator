"""Drop prospects the pipeline must not contact."""

from leadgen.schemas import Excluded, PipelineConfig, Prospect


def apply_exclusions(
    prospects: list[Prospect], pipeline: PipelineConfig
) -> tuple[list[Prospect], list[Excluded]]:
    """Split the list. One reason per person. do_not_contact wins if both match."""
    eligible: list[Prospect] = []
    excluded: list[Excluded] = []
    for prospect in prospects:
        if prospect.do_not_contact == pipeline.exclusions.do_not_contact_is:
            excluded.append(
                Excluded(prospect_id=prospect.prospect_id, reason="do_not_contact")
            )
        elif prospect.consent_status in pipeline.exclusions.consent_status_is:
            excluded.append(
                Excluded(prospect_id=prospect.prospect_id, reason="no_consent")
            )
        else:
            eligible.append(prospect)
    return eligible, excluded
