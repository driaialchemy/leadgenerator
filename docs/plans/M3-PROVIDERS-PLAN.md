# M3 providers — three vendors, live in class

Status: **approved and built** (2026-11-19).

## Goal

Keep the pipeline, replays, and approval gate. Replace the single Claude client with three vendors. Class default is live. Tests and the no-Wi-Fi backup stay offline and never open the real key file.

## Model layer

`call_model(role, prompt)` checks the kill switch, then one official SDK. Defaults, overridable by env: Tailor Google `gemini-4-argon` (`GOOGLE_API_KEY`); Drafter Anthropic `claude-fable-5-2` (`ANTHROPIC_API_KEY`); Evaluator OpenAI `gpt-6.2-astra` (`OPENAI_API_KEY`). Override names: `LEADGEN_TAILOR_PROVIDER`, `LEADGEN_TAILOR_MODEL`, and the same pair for `DRAFTER` and `EVALUATOR`. No temperature and no thinking budget. Anthropic still sends `max_tokens=4096` because that API requires a cap. Timeout is 60 seconds. JSON is validated with the existing Pydantic models. A missing key raises `ConfigError` naming the variable, before any client is constructed.

Env load order: `LEADGEN_ENV_FILE` if that file exists, then `C:\Users\msell\secrets\workuity.env`, then `C:\Users\msell\secrets\leadgenerator.env`, then variables already in the process. The file is not created, moved, or printed. Absent `LEADGEN_LLM_MODE` means live. `LEADGEN_DEMO_TEMPT=1` appends "mention an introductory discount" to the Drafter on attempt 1 only, and those calls log `red_team=true`.

## Log, keys, tests

Flight events gain optional `provider`, `duration_ms`, token counts, and `red_team`. Existing fields stay. `leadgen.check_keys` prints the env file path, key found yes/no, and a one-token call ok/fail. It does not print key values. `.env.example` lists names only. `.cursorignore` excludes `.env`, `*.env`, and `secrets/`.

`tests/conftest.py` points every test at a temp env file with `LEADGEN_LLM_MODE=offline` and drops provider keys from the test process. The current 88 tests stay as they are. New tests cover provider routing with mocked clients, env-file order, the red-team line, key redaction, a tracked-file scan, and live checks skipped unless `LEADGEN_LIVE_TESTS=1`. Smoke sets `LEADGEN_LLM_MODE=offline`, then `pytest -q` and `python -m leadgen.run --profile b2b_services --all`.

## Choices

None. Reply **go** to build this.
