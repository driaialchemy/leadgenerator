# Handoff

## Current milestone

M4 is done. The class page walks one prospect from the ranked list to an outbox file. Do not run git until asked.

## Done

- M1 scaffold and M2 scoring, findings, renderer, verifier, and funnel.
- Three vendors: Tailor on Google, Drafter on Anthropic, Evaluator on OpenAI. Live is the class default. Tests force offline and never open the real key file.
- One retry per run. A tailor-gate failure retries the tailor. A verifier or evaluator failure retries the drafter. B2B-001 and HOME-002 block on attempt 1 and pass on attempt 2. B2B-002 fails specificity once, then passes. B2B-004, HOME-001, and HOME-004 pass on the first attempt with the same findings as M2.
- B2B-003 and B2B-005 are refused. No run folder and no model call.
- `runs/flight_recorder.jsonl` is append-only. Retries record `attempt_number`, `retry_of`, and `retry_reason`.
- `python -m leadgen.check_keys` reports each provider without printing a key. `LEADGEN_DEMO_TEMPT=1` tempts the Drafter on attempt 1 only.
- Approval writes `outbox/<run_id>.txt` once. `REJECTED` writes nothing. The kill switch stops run and approve before a model call. The page calls `decide`, the same function the CLI prints.
- Replays live in `sample_data/replays/`. B2B-001 and HOME-002 reuse the caught fixture, then the good fixture.
- The class page is `src/leadgen/app.py`. Launch it with `powershell -ExecutionPolicy Bypass -File run_app.ps1`. The sidebar shows the mode, each role's provider and model, the red-team toggle, the kill switch, and Check keys.
- 108 tests pass, and 2 live tests stay skipped unless `LEADGEN_LIVE_TESTS=1`. No git.

## Next

No further milestone was requested. No git until asked.

## Known issues

None.
