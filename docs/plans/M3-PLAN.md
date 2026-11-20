# M3 Plan — Tailor, drafter, blind evaluator

Status: **approved and built** (2026-11-19).

## Goal

Three narrow roles, offline by default. Code scores, renders, verifies, logs, and applies the evaluator bar. A person signs. Ineligible prospects never reach a prompt.

## Flow

Refuse excluded or below-threshold prospects: one flight-recorder `refusal`, no run folder, zero model calls. Otherwise `runs/<prospect>-<UTC>/` holds `tailor.json`, `draft.json`, `rendered.txt`, `verification.json`, `evaluation.json`, and `status.json`. Order: tailor, re-read `tailor.json` and check claims and evidence, draft, render, re-read `draft.json` and call `verify`, then the evaluator. The evaluator receives only the rendered email and the profile's `buyer_persona`. Code marks it passing only when every score is at least `evaluator_pass_score`. The model does not return pass/fail.

One retry per run, on the first failure. A tailor-gate failure retries the tailor. A verifier or evaluator failure retries the drafter, then continues. The retry log has `attempt_number`, `retry_of`, and `retry_reason` (specificity is named when that score is under the bar). A second failure stops. Compliance still failing is `BLOCKED`. Quality still under the bar is `PENDING_APPROVAL` with `evaluator_below_bar` true. A clean pass is `PENDING_APPROVAL` with that flag false. B2B-001 is one tailor call, two drafter calls, one evaluator call.

`verifier.py`, scoring, findings, renderer, and the sample CSVs stay unchanged. The tailor gate calls the verifier's existing claim and evidence helpers.

## Model and files

Offline reads `sample_data/replays/<profile>/<prospect>/<role>.json` and `<role>.attempt2.json`. B2B-001 and HOME-002 use the caught fixture, then the good fixture. B2B-002 attempt 1 is generic; attempt 2 uses the notes. B2B-004, HOME-001, and HOME-004 pass on attempt 1. Live mode uses the Anthropic SDK and `LEADGEN_MODEL=claude-sonnet-5-5`, and raises `ConfigError` before any SDK call when the key or model is missing. The kill switch runs before every call and before approve.

New: `prompts/{tailor,drafter,evaluator}.md`, `llm.py`, `flight_recorder.py`, `gates.py`, `pipeline.py`, `run.py`, `approve.py`, `outbox.py`, plus `EvaluatorResult` and the log event on the existing schemas. Both profiles gain a one-sentence `buyer_persona`. Tailor input omits email and consent. No prompt contains an email address. Runs, the recorder, outbox, and replays take a root so tests use `tmp_path`.

## Approval

`leadgen.approve` accepts `APPROVED`, `EDITED`, or `REJECTED`, a name, and `--ack-findings`. It refuses a `BLOCKED` run, findings that were not acknowledged, an empty name, a second approval, a draft changed on disk after verification, and an edit that fails `verify` (including `50%`). `REJECTED` writes nothing. An accepted decision writes `outbox/<run_id>.txt` once, after re-reading the approval from disk. `outbox.py` imports no send or network library.

## Tests

The verification list, beside the existing 69 tests. Smoke: `pytest -q`, both `--all` runs, then approve B2B-004 as Demo Sales Manager with `--ack-findings`.

## Choices

None. Reply **go** to build this.
