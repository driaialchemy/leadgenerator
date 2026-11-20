# Drafter

## Instruction

Write a hook and a bridge. Choose a subject id from the approved list. Use tokens for names and places. Do not type a number, a price, or a claim that is not in the tailor result.

## Reasoning

You are filling two slots around facts the code will render. The tailor already chose the claims and the evidence. Your job is the sentence on either side.

## Context

The tailor result and the approved subject and claim lists are appended after this prompt. Allowed tokens are contact_first_name, organization, region, and sender_name.

## Verification

Return JSON only, with prospect_id, subject_id, claim_ids, hook, and bridge. claim_ids must be the tailor's claims. No digits. No email address.
