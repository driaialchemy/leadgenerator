# Codex handoff: Lead & Income Generation Workflow

Repo: `C:\Users\msell\OneDrive\aialchemyrepos\workuity\leadgenerator`
Read `AGENTS.md` first. It holds the rules. `HANDOFF.md` is the running status log.
Public repo: https://github.com/driaialchemy/leadgenerator

## Environment

- Windows, PowerShell, Python 3.11
- venv: `.\.venv\Scripts\python.exe` (package installed editable as `leadgen`)
- Tests: `pytest -q` (last known: 171 passed, 2 skipped; the skips run only with `LEADGEN_LIVE_TESTS=1`)
- Launch the page: `powershell -ExecutionPolicy Bypass -File run_app.ps1` (app is `src/leadgen/app.py`)
- Other checks: `python -m leadgen.validate_samples`, `python -m leadgen.check_keys` (reports each provider without printing a key)
- Keys and mail tokens live in `C:\Users\msell\secrets`. Never print or copy them. Live search needs `SAM_API_KEY`, `LEADGEN_EDGAR_USER_AGENT`, and optionally `CENSUS_API_KEY`.

## What this app is

A teaching demo. Code decides who to contact. The AI writes only from an approved fact sheet. Code inspects every draft. A human signs before anything leaves.

- Three vendors: Tailor on Google, Drafter on Anthropic, Evaluator on OpenAI. Tests force offline and never open the real key file.
- Pipeline: Find, Shortlist, Draft, Review, Send. One retry per run (tailor-gate failure retries the tailor; verifier or evaluator failure retries the drafter).
- Search reads SAM.gov, SEC EDGAR, and City of Phoenix permits. A failing source does not stop the others.
- Scoring (code only): 30 in service area, 25 named contact, 25 recent permit, 20 industry likely to hire commercial plumbing.
- Send offers Practice (outbox file), Gmail (compose scope), Outlook (`Mail.Send`, `Mail.ReadWrite`). The code never lists or reads messages. See `docs/EMAIL_SETUP.md`.
- Profile: `config/profiles/acme_plumbing.yaml` is the only one. Sender name, postal address, and phone are placeholders, so Gmail and Outlook Send now is refused until they are real. Approved price: "$150 per hour plus parts".

## State

M11.1 is done locally and not pushed. Search results are businesses, not permit rows: names come from company fields or valid site names, irrelevant permits are left out and counted, repeat businesses collapse to one row, a contact shows only for a real person's name, and scores spread 44 to 76 on live data. M10, M11, M12, and M11.1 are local commits on top of `origin/main`. M6 through M9 are already on `main`.

## Open items

None is mandatory. Ask the owner which to do before starting any of them.

- **Push**: only when the owner replies "approved push". Do not push otherwise.
- **Hero photo**: the owner supplies `assets/source/hero_shower.jpg` (git-ignored). Until then the hero is a blue-to-cyan gradient with a water drop. The first render with a photo writes `assets/hero_shower_web.jpg`, under 150 KB, and reuses it. Nothing to code unless rendering breaks.
- **Contacts**: permit sources give a site name or contractor company and no email, so drafts work but nothing can be sent. Any change here must not invent contact data.
- **Stale runs**: old runs from removed profiles remain in `runs/` and `outbox/`. The tiles skip them. Do not delete them without asking.

## Do not

- Import `anthropic`, `requests`, `httpx`, or any network/AI library in `verifier.py`, `scoring.py`, `metrics.py`, `exclusions.py`, `findings.py`, `renderer.py`, or `phrases.py`.
- Import `smtplib` anywhere. Gmail and Outlook are called only from the mail gate (`deliver`), after an approval record.
- Name an industry or profile id in the Python package. Industry content lives only in `config/profiles/*.yaml`.
- Let the AI write facts, prices, or claims. Prospect facts are `{{tokens}}` rendered by code. Claims are chosen by ID from the approved list.
- Weaken a mail safeguard: approval record, second confirmation, Demo safety, allowlist, one confirmed send per run, session send cap, opt-out line and sender identity, kill switch.
- Bypass `assert_not_engaged()`. The kill switch is `LEADGEN_KILL_SWITCH=1` or a `KILL_SWITCH` file. Only the value `1` counts.
- Edit tests to make them pass. Fix code.
- Commit `.env` or copy public-record data into the repo.
- Run git push without the owner's "approved push".

## Done means

1. `pytest -q` is green (2 live skips expected).
2. `python -m leadgen.validate_samples` passes.
3. `HANDOFF.md` is updated.

## Paste prompt

```
Repo: C:\Users\msell\OneDrive\aialchemyrepos\workuity\leadgenerator
Read AGENTS.md and CODEX_HANDOFF.md. The project is at M11.1, local only. Before changing anything, run pytest -q and report the result, then ask me which open item in CODEX_HANDOFF.md to do. Fix code, not tests. Never print keys. Do not push unless I reply "approved push". Update HANDOFF.md when done.
```
