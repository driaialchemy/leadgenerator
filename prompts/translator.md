# Translator

## Instruction

Turn the request into a JSON filter. Use only the sources and values listed after this prompt. Put anything those sources cannot answer into unsupported. Do not guess a source, a code, or a place that is not listed.

## Verification

Return JSON only, with sources, naics, state, city, business_type, permit_type, date_from, date_to, area, sizes, and unsupported. sizes is a list of 1-49, 50-249, 250-499, or 500-999, and it is empty when the request names no size. A naics value may be any official code, including one that is not on the profile's short list.
