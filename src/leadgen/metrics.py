"""Funnel counts from past outcomes. Code does the arithmetic."""

from leadgen.schemas import Funnel, Outcome


def funnel(outcomes: list[Outcome]) -> Funnel:
    """Count how far each past outreach went. Rates are fractions of sent."""
    sent = len(outcomes)
    replied = 0
    meeting = 0
    won = 0
    won_value = 0
    for outcome in outcomes:
        stage = outcome.furthest_stage
        if stage in {"replied", "meeting", "won", "lost_after_meeting"}:
            replied += 1
        if stage in {"meeting", "won", "lost_after_meeting"}:
            meeting += 1
        if stage == "won":
            won += 1
            won_value += outcome.deal_value or 0
    return Funnel(
        sent=sent,
        replied=replied,
        meeting=meeting,
        won=won,
        won_value=won_value,
        reply_rate=_rate(replied, sent),
        meeting_rate=_rate(meeting, sent),
        win_rate=_rate(won, sent),
        avg_deal=round(won_value / won, 2) if won else 0,
    )


def _rate(count: int, sent: int) -> float:
    if sent == 0:
        return 0
    return count / sent
