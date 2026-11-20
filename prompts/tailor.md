# Tailor

## Instruction

Pick 1 or 2 claim ids from the approved list. For each claim, quote words that appear in the notes. Do not invent facts, prices, or claims.

## Reasoning

The notes are messy. The claim list is the only shelf you may use. A quote that is not in the notes will be sent back.

## Context

Notes, attributes, and the approved claims are appended after this prompt. You do not receive an email address or a consent field.

## Verification

Return JSON only, with prospect_id, claim_ids, and evidence. Each evidence item has claim_id and quote. The quote is at least two words copied from the notes.
