# Handoff

## Current milestone

M9 done locally, not pushed. An approved note can be saved as a Gmail or Outlook draft, or sent from that account. Practice still writes one outbox file. Five local commits are waiting. The public repo is https://github.com/driaialchemy/leadgenerator.

## Done

- M1 scaffold and M2 scoring, findings, renderer, verifier, and funnel.
- Three vendors: Tailor on Google, Drafter on Anthropic, Evaluator on OpenAI. Live is the class default. Tests force offline and never open the real key file.
- One retry per run. A tailor-gate failure retries the tailor. A verifier or evaluator failure retries the drafter. B2B-001 and HOME-002 block on attempt 1 and pass on attempt 2. B2B-002 fails specificity once, then passes. B2B-004, HOME-001, and HOME-004 pass on the first attempt with the same findings as M2.
- B2B-003 and B2B-005 are refused. No run folder and no model call.
- `runs/flight_recorder.jsonl` is append-only. Retries record `attempt_number`, `retry_of`, and `retry_reason`.
- `python -m leadgen.check_keys` reports each provider without printing a key. `LEADGEN_DEMO_TEMPT=1` tempts the Drafter on attempt 1 only.
- Approval writes `outbox/<run_id>.txt` once. `REJECTED` writes nothing. The kill switch stops run and approve before a model call. The page calls `decide`, the same function the CLI prints.
- Replays live in `sample_data/replays/`. B2B-001 and HOME-002 reuse the caught fixture, then the good fixture.
- The class page is `src/leadgen/app.py`. Launch it with `powershell -ExecutionPolicy Bypass -File run_app.ps1`. The steps are Find, Shortlist, Draft, Review, and Send. The sidebar is the business, Practice data or Live, and More. More holds the logbook, the funnel, and Settings. Settings holds the model for each step, the red-team toggle, Check keys, Demo safety, and the Gmail and Outlook connection. The page says "Waiting for your approval" and does not ship an image.
- Send offers Practice, Gmail, and Outlook. Practice is the outbox file written at approval. Gmail uses the compose scope. Outlook uses delegated `Mail.Send` and `Mail.ReadWrite`. The code never lists or reads messages. Tokens stay in `C:\Users\msell\secrets`. See `docs/EMAIL_SETUP.md`.
- Mail safeguards live in `deliver`: an approval record, a second confirmation, Demo safety, the signed-in address on the allowlist, one confirmed send per run, a session send cap, no email means no mailbox action, the opt-out line and sender identity, and the kill switch. A provider must return a message id before the note is marked sent.
- Search reads SAM.gov, SEC EDGAR, and City of Phoenix permits. Offline replays trimmed fixtures. A source that fails does not stop the others.
- 165 tests pass, and 2 live tests stay skipped unless `LEADGEN_LIVE_TESTS=1`. Mail tests use fake Gmail and Graph clients.
- Published on `main` at https://github.com/driaialchemy/leadgenerator.
- Three more profiles: workflow studio, admin desk, and local-letter sponsors. Each has six synthetic prospects and eight outcome rows. Scoring, the verifier, and approval are unchanged. The picker uses `menu_order` so the original profile stays first.

## Next

M6, M7, M8, M8.1, and M9 are local commits. Wait for "approved push" before pushing anything.

## Known issues

None.
