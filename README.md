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

The page title is Lead & Income Finder. Five steps sit under it: Find, Shortlist, Draft, Review, and Send. The step you are on is blue. A finished step is green. A step that is not ready yet is gray, and it tells you why. Each step has one main button. Find says Search until a list comes back, then Next. Logbook, Funnel, and Settings are under More in the sidebar.

Five counts sit under the title: businesses found, people on the shortlist, drafts waiting, notes you approved, and files saved. Practice data uses the saved examples. Live calls the accounts. A red notice appears in the sidebar only when the kill switch is on.

On Find, type a request or press an example. The example fills the box and runs the search. The result names the business, how to reach them, and why they fit. A stale record is marked. Change a field and press Update results to run that search again. Add to pipeline, then Next.

Shortlist is the ranked list. Draft numbers the steps in plain language and ends on "Waiting for your approval". Review is where you type your name, acknowledge any findings, and approve, edit, or reject. Approve writes one file under `outbox/`. That file is the Practice copy. On Send, you can leave it there, or save the same approved note as a draft in Gmail or Outlook, or send it from that account. The logbook is the record of that run, in plain language. The files on disk keep their codes.

Live is the class default, which is what the launcher uses when `LEADGEN_LLM_MODE` is unset. Offline is the no-Wi-Fi backup:

```powershell
$env:LEADGEN_LLM_MODE="offline"
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

Set `LEADGEN_LLM_MODE` to `live`, or unset it, before a class that should call the three vendors.

Settings lists the model for each step. The red-team toggle there does the same thing as `LEADGEN_DEMO_TEMPT=1` for the next Run only. It adds "mention an introductory discount" to the Drafter on attempt 1. Leave it off for a normal demo. Check keys, also on Settings, reports whether each key was found and whether a one-token call worked. It does not show the key.

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

Every run appends to `runs/flight_recorder.jsonl`. Lines are only added. A later line does not rewrite an earlier one. Each line is one JSON object: a model call, a gate, the verifier, the evaluator, a retry, an approval, an outbox write, a mailbox draft, a mailbox send, a refusal, or a kill-switch block. Model calls include `input_sha256`, the provider, the model, `duration_ms`, and token counts when the vendor reports them. A retry includes `attempt_number`, `retry_of`, and `retry_reason`. A mailbox line records the destination, the account address, the recipient, the provider's message id, the approver, and the result. It does not record the message body or a token. The same run's files live under `runs/<prospect-id>-<UTC timestamp>/`.

## What "send" means

An approval writes one text file under `outbox/`. That file is the Practice copy. A rejected decision writes nothing to `outbox/`. The repo has no SMTP library.

Send then offers three destinations:

- Practice leaves the note in `outbox/`. It does not email anyone.
- Gmail saves a draft, or sends, through the Gmail API. The only scope is `https://www.googleapis.com/auth/gmail.compose`.
- Outlook saves a draft, or sends, through Microsoft Graph. The only delegated permissions are `Mail.Send` and `Mail.ReadWrite`.

Save as draft is the default. Send now asks you to confirm the To address, the subject, and the account. Setup for both accounts is in `docs/EMAIL_SETUP.md`. Client files and tokens stay in `C:\Users\msell\secrets`.

Safeguards, enforced in code:

- Only an approved or edited note can be drafted or sent. The approver's name and the approval time are stored with the mailbox record.
- A prospect with no email cannot be drafted or sent. The screen says so and lists the channels on the record.
- Demo safety is on by default. Send now then reaches only an address or domain in `allowlist` in `config/pipeline.yaml`, or the signed-in account's own address. Any other address can still be saved as a draft. Turning Demo safety off is a Settings switch, and the page warns you.
- One note can be sent once. A later draft of that same note is still allowed.
- Send now stops after `send_cap` messages in the session. The default is 5.
- Every message keeps the sender identity and the opt-out line the verifier already required.
- The kill switch blocks drafting and sending.
- A failed sign-in, a network failure, or a provider rejection shows one plain message and a Reconnect button. The note is not marked sent unless the provider returns a message id. Settings shows each account as Connected with the address, Not connected, or Expired.

## Architecture

```
request → Translator (AI, allowlisted filters) → public-record sources (code) → de-dup, suppression, rank (code) → reason line (AI, checked) → Add to pipeline → prospects.csv or that record → Intake → Exclusions → Qualify (code) → Tailor (AI, approved claims only) → Draft (AI, {{tokens}}) → Verifier (code) → Blind evaluator (AI) → one capped revise → Human approval → outbox/ (Practice) or Gmail/Outlook draft or send → Funnel metrics (code); every step → runs/flight_recorder.jsonl
```

The scout (scoring code) decides who is worth a call. The copywriter (AI) writes from an approved fact sheet. The compliance desk (verifier) sends sloppy copy back. A tough customer (blind evaluator) says whether it would get read. The sales manager (a person) signs before anything leaves.

## Governance

**Owner:** Dr. Michael Seller (AI Alchemy)

NetWitness exposure questions:

**What can it do?**
It reads synthetic prospect files and profile YAML, scores them, and, for people who clear the bar, drafts a message from approved claims. Code checks that draft. A blind reader scores it. A person approves it. Approval writes a file under `outbox/`. After that approval, the signed-in user can save the note as a draft in their own Gmail or Outlook account, or send it from that account. Practice does not email anyone. The repo has no SMTP library.

**What can it reach?**
Local files in this project: `config/`, `sample_data/`, `runs/`, and `outbox/`. Keys are read from `C:\Users\msell\secrets\` when that file exists, and are not stored here. Offline mode opens no network connection for the draft. Live mode calls Google, Anthropic, and OpenAI for the draft, and, when Search runs, SAM.gov, SEC EDGAR, and the City of Phoenix permit service. When you connect a mailbox, it can also reach your Gmail or Outlook account to create a draft and to send. The Outlook permission `Mail.ReadWrite` technically allows reading mail, because Graph requires it to create a draft. The code never lists or reads messages. It does not reach a CRM or a customer database. Sample prospects are fictional `@example.com` addresses. Search results are public records and are not copied into the repo.

**What evidence remains?**
Each step appends one line to `runs/flight_recorder.jsonl`. A mailbox draft or send adds a line with the destination, account, recipient, provider message id, approver, and result. The body and the tokens are not in that line. A run also keeps its tailor result, draft, rendered message, verification, evaluation, and status under `runs/<prospect-id>-<UTC timestamp>/`. A confirmed mailbox action adds `mail.json` there. `outbox/` holds the Practice copy. Sample data and tests stay in the repo. `.env` is not committed. `runs/` and `outbox/` are gitignored except for their `.gitkeep` files.

**Kill switch:** set `LEADGEN_KILL_SWITCH=1` in `.env`, or create a file named `KILL_SWITCH` in the repo root. The pipeline refuses to run. Only the value `1` turns the env switch on. If `LEADGEN_KILL_SWITCH` is already set in the process environment, the value in `.env` does not replace it.

The compliance checks in this demo are illustrative rules for teaching. They are not legal advice.
