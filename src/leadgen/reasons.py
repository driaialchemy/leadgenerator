"""Check that a one-line reason only uses words from the public record."""

import re

from leadgen.sources.records import PublicRecord

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    """
    a an the and or of in on for to with this that from is has have was were
    recent filing permit named contact mailing address phone business record
    matches requested city state source public records registration updated
    naics uei project contractor at by its their your our search window days
    ago as it be are not no
    """.split()
)


def reason_is_grounded(reason: str, record: PublicRecord) -> bool:
    """True when every word is a stopword or appears on the record."""
    if not reason.strip():
        return False
    allowed = set(_WORD.findall(_blob(record)))
    for word in _WORD.findall(reason.casefold()):
        if word in _STOP or word in allowed:
            continue
        return False
    return True


def _blob(record: PublicRecord) -> str:
    parts = [
        record.business_name,
        record.uei,
        record.domain,
        record.contact_name,
        record.contact_title,
        record.phone,
        record.mailing_address,
        record.city,
        record.state,
        record.project,
        record.permit_type,
        record.permit_value,
        record.contractor,
        record.source,
        " ".join(record.naics),
        " ".join(record.business_types),
    ]
    if record.record_date is not None:
        parts.append(record.record_date.isoformat())
    if record.filing_date is not None:
        parts.append(record.filing_date.isoformat())
    if record.permit_date is not None:
        parts.append(record.permit_date.isoformat())
    return " ".join(parts).casefold()
