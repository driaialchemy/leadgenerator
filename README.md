# Lead & Income Generation Workflow

A teaching demo for business owners. Code decides who to contact. The AI writes only from an approved fact sheet. Code inspects every draft. A person signs before anything leaves the building.

Five fictional businesses live in profile files, not in the Python. Copperline IT Services is a managed-IT shop. Desert Peak Heating & Cooling is a home-services shop. Northloop Workflow Studio builds small workflows for local offices. Clearfile Admin Desk organizes files and first-pass letters, and a person reviews the work before it goes out. Valley Desk Letter sells sponsor slots in a local letter. Swap the profile and the scoring rules, approved claims, and sender change. The code stays the same.

Adding a business is a YAML file in `config/profiles/` plus a `prospects.csv` and an `outcomes.csv` under `sample_data/<profile_id>/`. The income-model profiles ban earnings language, including `$` and `%`. Their approved claims describe the service, not a result.

Sample people use `@example.com` addresses. Nothing here is a real contact.

## Setup and tests

Requires Python 3.11. From this folder, in PowerShell:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q; python -m leadgen.validate_samples
```

Check the sample files on their own:

```powershell
python -m leadgen.validate_samples
```

Run every sample prospect offline, then sign one:

```powershell
python -m leadgen.run --profile b2b_services --all
python -m leadgen.run --profile home_services --all
python -m leadgen.approve --profile b2b_services --prospect B2B-004 --latest --name "Demo Sales Manager" --decision APPROVED --ack-findings
```

Rank a profile without calling a model:

```powershell
python -m leadgen.qualify --profile b2b_services
```

## Class page

Launch the walkthrough from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

The sidebar shows Live or Offline, and the provider and model for the Tailor, Drafter, and Evaluator. Pick a profile, open Run, and press Run for one draft-eligible prospect. Review shows the email, the two attempts when a retry happened, and the evaluator scores. Approve, Edit, or Reject. Approve writes one file under `outbox/` after a named person acknowledges any findings. The logbook lists that run's flight-recorder lines.

Live is the class default, which is what the launcher uses when `LEADGEN_LLM_MODE` is unset. Offline is the no-Wi-Fi backup:

```powershell
$env:LEADGEN_LLM_MODE="offline"
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

Set `LEADGEN_LLM_MODE` to `live`, or unset it, before a class that should call the three vendors.

The sidebar red-team toggle does the same thing as `LEADGEN_DEMO_TEMPT=1` for the next Run only. It adds "mention an introductory discount" to the Drafter on attempt 1. Leave it off for a normal demo. Check keys, in the sidebar, reports whether each key was found and whether a one-token call worked. It does not show the key.

## Public records

Search reads three public sources. It does not scrape pages and it does not guess an email or a phone number.

| Source | What a search can ask | What a record can contain |
| --- | --- | --- |
| SAM.gov Entity Management API | NAICS, state, city, business type, or an exact business name | Business name, UEI, addresses, NAICS, registration dates, and a point of contact's name, title, and mailing address |
| SEC EDGAR submissions | Exact business name, after another source has already found the company | Company facts and a recent-filing signal |
| City of Phoenix ShapePHX permit points | Permit type, issue-date range, and area | Project, address, permit type, issue date, and the contact or owner |

SAM.gov needs a free public API key. Create an account at [sam.gov](https://sam.gov), open your profile, and request a public API key. Put it in `SAM_API_KEY` in the secrets file named above. Leave it out of this repo. A personal key allows about 10 requests a day, so each response is cached under `runs/source_cache/` for 24 hours. The cache file does not contain the key.

EDGAR does not use a key. Set `LEADGEN_EDGAR_USER_AGENT` to a short string that names this demo and how to reach you, as the SEC asks callers to do. That value is sent as the User-Agent header and is not printed, logged, or cached. A company is included only when its normalized name is an exact match in the SEC ticker file. A miss means no EDGAR facts for that company.

Public records do not contain a personal email, a private phone number, a consent flag, or the scoring attributes on a profile. SAM point-of-contact phone and email are not public, so they are not copied. The Phoenix permit layer used here does not publish a project value, so that field stays blank. A record with no email can still be drafted and approved. The approval screen lists the channels the record does have, and the outbox file says "No email on record". The existing score and exclusion rules still decide whether a draft is allowed.

Offline mode replays small fixture files shaped like the live responses and makes no network call. If one source times out or is rate limited, the page shows one sentence naming that source and keeps the records from the others.

## Live mode

Class demos call three vendors. The Tailor uses Google (`gemini-4-argon`). The Drafter uses Anthropic (`claude-fable-5-2`). The Evaluator uses OpenAI (`gpt-6.2-astra`). If `LEADGEN_LLM_MODE` is unset, the mode is live.

Keys live outside this repo and outside OneDrive. The program loads the first file that exists: `LEADGEN_ENV_FILE`, then `C:\Users\msell\secrets\workuity.env`, then `C:\Users\msell\secrets\leadgenerator.env`. It then uses variables already in the process. Do not copy that file into the repo. `.env.example` lists the variable names only.

Check the three keys without printing them:

```powershell
python -m leadgen.check_keys
```

Each line says whether the key was found and whether a one-token call succeeded.

Offline mode is the no-Wi-Fi backup and the way the tests run. It reads `sample_data/replays/` and makes no network call:

```powershell
$env:LEADGEN_LLM_MODE="offline"
python -m leadgen.run --profile b2b_services --all
```

A missing key raises `ConfigError` naming the variable, before any client is constructed. The kill switch is checked first.

## Red-team switch

Set `LEADGEN_DEMO_TEMPT=1`, or turn on the sidebar red-team toggle, to add one visible line to the Drafter on attempt 1: "mention an introductory discount." The flight recorder marks those calls with `red_team` true. Attempt 2 does not get the line. The toggle applies only to the next Run. Leave the switch unset during a normal demo.

## Logbook

Every run appends to `runs/flight_recorder.jsonl`. Lines are only added. A later line does not rewrite an earlier one. Each line is one JSON object: a model call, a gate, the verifier, the evaluator, a retry, an approval, an outbox write, a refusal, or a kill-switch block. Model calls include `input_sha256`, the provider, the model, `duration_ms`, and token counts when the vendor reports them. A retry includes `attempt_number`, `retry_of`, and `retry_reason`. The same run's files live under `runs/<prospect-id>-<UTC timestamp>/`.

## What "send" means

An approval writes one text file under `outbox/`. That file is the message. Nothing is emailed or texted. The repo has no SMTP library. A rejected decision writes nothing to `outbox/`.

## Architecture

```
request → Translator (AI, allowlisted filters) → public-record sources (code) → de-dup, suppression, rank (code) → reason line (AI, checked) → Add to pipeline → prospects.csv or that record → Intake → Exclusions → Qualify (code) → Tailor (AI, approved claims only) → Draft (AI, {{tokens}}) → Verifier (code) → Blind evaluator (AI) → one capped revise → Human approval → outbox/ (no real send) → Funnel metrics (code); every step → runs/flight_recorder.jsonl
```

The scout (scoring code) decides who is worth a call. The copywriter (AI) writes from an approved fact sheet. The compliance desk (verifier) sends sloppy copy back. A tough customer (blind evaluator) says whether it would get read. The sales manager (a person) signs before anything leaves.

## Governance

**Owner:** Dr. Michael Seller (AI Alchemy)

NetWitness exposure questions:

**What can it do?**
It reads synthetic prospect files and profile YAML, scores them, and, for people who clear the bar, drafts a message from approved claims. Code checks that draft. A blind reader scores it. A person approves it. Approval writes a file under `outbox/`. It cannot send email or SMS. The repo has no SMTP library.

**What can it reach?**
Local files in this project: `config/`, `sample_data/`, `runs/`, and `outbox/`. Keys are read from `C:\Users\msell\secrets\` when that file exists, and are not stored here. Offline mode opens no network connection. Live mode calls Google, Anthropic, and OpenAI for the draft, and, when Search runs, SAM.gov, SEC EDGAR, and the City of Phoenix permit service. It does not reach a CRM, a mailbox, or a customer database. Sample prospects are fictional `@example.com` addresses. Search results are public records and are not copied into the repo.

**What evidence remains?**
Each step appends one line to `runs/flight_recorder.jsonl`. A run also keeps its tailor result, draft, rendered message, verification, evaluation, and status under `runs/<prospect-id>-<UTC timestamp>/`. `outbox/` holds the files that stand in for sending. Sample data and tests stay in the repo. `.env` is not committed. `runs/` and `outbox/` are gitignored except for their `.gitkeep` files.

**Kill switch:** set `LEADGEN_KILL_SWITCH=1` in `.env`, or create a file named `KILL_SWITCH` in the repo root. The pipeline refuses to run. Only the value `1` turns the env switch on. If `LEADGEN_KILL_SWITCH` is already set in the process environment, the value in `.env` does not replace it.

The compliance checks in this demo are illustrative rules for teaching. They are not legal advice.
