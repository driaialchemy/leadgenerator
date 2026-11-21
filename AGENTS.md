# Agent rules — Lead & Income Generation Workflow

## Purpose

Teaching demo for business owners. Code decides who to contact, the AI writes only from an approved fact sheet, code inspects every draft, and a human signs before anything leaves.

## Layout

- `src/leadgen/` — the Python package
- `config/pipeline.yaml` — draft threshold, tiers, revision cap, exclusions
- `config/profiles/` — one YAML file per domain
- `sample_data/<profile_id>/` — synthetic prospects and past outcomes
- `tests/` — pytest
- `runs/` — later, the append-only flight recorder
- `outbox/` — later, the only place a "sent" email is written

`pyproject.toml` sets pytest `pythonpath = ["src"]`.

## Probabilistic / deterministic boundary

- Probabilistic steps (tailor, draft, blind evaluator) may pick an approved claim id or subject id, and may fill template slots around `{{tokens}}`.
- Deterministic steps (schema checks, exclusions, scoring, verifier, funnel metrics, kill switch) are plain Python.
- The AI never writes facts, prices, or claims. Prospect facts appear only as `{{tokens}}` rendered by code, and claims are selected by ID from the profile's approved list.

## Verifier, scoring, and metrics

`src/leadgen/verifier.py`, `scoring.py`, `metrics.py`, `exclusions.py`, `findings.py`, `renderer.py`, and `phrases.py` may not import anthropic, requests, httpx, or any network/AI library.

## Sending

No module may import smtplib. Practice approval still writes one file under `outbox/`. Gmail and Outlook are called only from the mail gate, after an approval record. The Gmail scope is compose. The Graph permissions are `Mail.Send` and `Mail.ReadWrite`. The verifier, scoring, and metrics modules do not import those clients.

## Profiles

Industry-specific content lives only in `config/profiles/*.yaml`. The Python package does not name an industry or a profile id.

## Writes

File and record writes are single-threaded.

## Data

Sample prospects are synthetic. Live search reads public-record APIs and caches responses under `runs/`, which is gitignored. It does not copy those records into the repo.

## Secrets

Never commit `.env`.

## Tests

Don't modify tests to make them pass. Fix the code.

From the repo root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
python -m leadgen.validate_samples
python -m leadgen.qualify --profile <id>
```

## Kill switch

If `LEADGEN_KILL_SWITCH=1` (environment or `.env`) or a file named `KILL_SWITCH` exists in the repo root, the pipeline must refuse to run. Do not bypass `assert_not_engaged()`. Loading `.env` must not override a variable that is already set. Only the value `1` counts.
