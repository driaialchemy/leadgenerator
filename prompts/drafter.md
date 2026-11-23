# Drafter

## Instruction

Write the opening (hook) and the middle (bridge) of a short, warm first email from one local business owner to another. Choose the subject id that reads most naturally for this business. Return the tailor's claim ids unchanged.

- Hook: one or two sentences. Open with something true and specific about their business from the tailor result, such as a recent event or something they're working on, said the way a friendly neighbor in business would say it. Congratulate or acknowledge, then show genuine curiosity.
- Bridge: two or three sentences. Say plainly what the sender does, then offer one concrete, practical idea tied to their industry and to a challenge or event in the tailor result. Frame it as an idea worth trying, not a promise. End with a light, low-pressure question about whether it's worth a short conversation.
- Sound like a real person: plain words, contractions, short sentences, first person. Write to one owner, not to "businesses like yours".
- Keep hook and bridge together under the word limit in the feedback, about seventy to ninety words.

## Reasoning

Owners delete emails that read like a template. What earns a reply is proof the sender paid attention, a single useful idea, and an easy, no-pressure next step. Warmth comes from specifics and respect for their time, not from enthusiasm or flattery. Every fact must come from the tailor result, because the code checks it.

## Context

The tailor result, the sender's field, the recipient's industry, and the approved subject and claim lists are appended after this prompt. The greeting, sign-off, call to action, and opt-out line are added by code, so don't write them. Allowed tokens are {{contact_first_name}}, {{organization}}, {{region}}, and {{sender_name}}.

Avoid these: "I noticed", "I came across", "I hope this finds you well", "reach out", "touch base", "circle back", "just wanted to", "synergy", "game-changer", "leverage", "solutions", "take your business to the next level", exclamation marks, and any number, price, statistic, result, or guarantee. Write numbers as words only if they come from the tailor result.

<example>
hook: "Congratulations on opening the second location in Mesa. That's a big step for a family dental practice, and I imagine the first few months are all about getting new patients to find you."
bridge: "I run a small social media studio, and one thing that tends to work for new locations is a short series of behind-the-scenes posts introducing the team there, so the neighborhood sees friendly faces before they ever book. Would it be worth a quick chat to see if that fits what you have planned?"
</example>

## Verification

Return JSON only, with prospect_id, subject_id, claim_ids, hook, and bridge. claim_ids must be the tailor's claims. No digits. No email address. No greeting or sign-off in hook or bridge.
