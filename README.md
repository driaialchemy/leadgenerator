# Acme Plumbing prospecting

Code decides who to contact. The AI writes only from an approved fact sheet. Code inspects every draft. A person signs before anything is saved or sent.

The business is Acme Plumbing, in `config/profiles/acme_plumbing.yaml`. It serves Greater Phoenix and Greater Tucson. The approved rate is exactly "$150 per hour plus parts". The sender name, postal address, and phone in that file are placeholders. While any of those three is still a placeholder, Gmail and Outlook Send now is refused. Drafts and Practice still work.

The shortlist is the businesses you add from a search. It is saved in `runs/shortlist.json`. There is no sample prospect list on the screen.

## Setup and tests

Requires Python 3.11. From this folder, in PowerShell:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q; python -m leadgen.validate_samples
```

Check the sample files on their own:

```powershell
python -m leadgen.validate_samples
```

Acme Plumbing is searched from the page. It has no sample prospect file.

Rank the fixture sample list without calling a model:

```powershell
python -m leadgen.qualify --profile b2b_services
```

## The page

Launch it from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

The page title is Acme Plumbing. Five steps sit under it: Find, Shortlist, Draft, Review, and Send. The step you are on is red. A finished step is green. A step that is not ready yet is gray, and it tells you why. Each step has one main button. Find says Search until a list comes back, then Next. Logbook, Funnel, and Settings are under More in the sidebar.

Five counts sit under the title: businesses found, businesses on the shortlist, drafts waiting, notes you approved, and files saved. Live is the mode on screen. A red notice appears in the sidebar only when the kill switch is on.

On Find, pick metro areas and, if you want, an industry and a size, then press Search. The written request box is optional. It is read only when it has text. If that reading fails, the search still runs from the fields on screen. The industry box suggests official titles, including a misspelling, and lets you keep chips. Employee size is 1–49, 50–249, 250–499, 500–999, or any size. Each source has a status line with a count or the reason it returned none. Add one business, or Add all shown, then Next.

Shortlist shows the businesses you added: name, city, industry, contact, channels, score, and fit. A refresh keeps the list. Draft numbers the steps in plain language and ends on "Waiting for your approval". Review is where you type your name, acknowledge any findings, and approve, edit, or reject. Approve writes one file under `outbox/`. That file is the Practice copy. On Send, you can leave it there, or save the same approved note as a draft in Gmail or Outlook, or send it from that account. Send now is refused until the settings file has a real sender name, address, and phone. The logbook is the record of that run, in plain sentences.

Live is the default, which is what the launcher uses when `LEADGEN_LLM_MODE` is unset. Offline is for tests:

```powershell
$env:LEADGEN_LLM_MODE="offline"
powershell -ExecutionPolicy Bypass -File run_app.ps1
```

Set `LEADGEN_LLM_MODE` to `live`, or unset it, before a search that should call the three vendors.

Settings lists the model for each step. Check keys reports whether each key was found and whether a one-token call worked. It does not show the key. Allowlist only, on by default, blocks Send now to anyone except the allowlist or the signed-in account.

## Public records

Search reads public sources. It does not scrape pages and it does not guess an email, a phone number, or a headcount.

The industry box matches what you type, including a misspelling, to an official 2022 NAICS title. A single word inside a title is enough. You can keep more than one chip. Leaving the industry blank searches every industry. The words you type are not put in a request URL.

SAM.gov is queried once for Arizona. The metro cities are kept in code. Each search may use at most 5 SAM pages, set by `sam_page_budget`. A rate limit or a daily limit stops SAM, keeps the rows already fetched, and the status line says "SAM.gov daily limit reached; results resume tomorrow". Phoenix and Tucson permits use their larger ArcGIS page sizes, up to the 200-record cap.

Employee size uses the Census size classes 1–49, 50–249, 250–499, and 500–999. Leave the selector empty for any size. "Only show businesses with a known size" hides records that do not carry a headcount. The app does not estimate one. In live mode a line under the size selector points you to the Market size cards.

The Market size cards are county totals, not a list of businesses. With an industry selected, one card covers Maricopa County and one covers Pima County, both in Arizona, from County Business Patterns for 2023. A free `CENSUS_API_KEY` is optional. The cache does not contain the key. If County Business Patterns does not respond, the page says so in one sentence and the business search still returns. Tucson commercial permits come from the City of Tucson `PDSD_CommercialBldg` layer. There is no separate Pima County permit feed.

| Source | What a search can ask | What a record can contain |
| --- | --- | --- |
| SAM.gov Entity Management API | NAICS, state, city, business type, or an exact business name | Business name, UEI, addresses, NAICS, registration dates, and a point of contact's name, title, and mailing address. No headcount. |
| SEC EDGAR submissions | Exact business name, after another source has already found the company | Company facts and a recent-filing signal. No headcount. |
| City of Phoenix ShapePHX permit points | A permit type mapped from the chosen industry, an issue-date range, and an area | Project, address, permit type, issue date, and the contact or owner. No headcount. |
| County Business Patterns | An official NAICS code and the profile county | Establishment counts by size band for that county and year. Not a list of businesses. |

SAM.gov needs a free public API key. Create an account at [sam.gov](https://sam.gov), open your profile, and request a public API key. Put it in `SAM_API_KEY` in the secrets file named above. Leave it out of this repo. A personal key allows about 10 requests a day, so each response is cached under `runs/source_cache/` for 24 hours. The cache file does not contain the key.

EDGAR does not use a key. Set `LEADGEN_EDGAR_USER_AGENT` to a short string that names this demo and how to reach you, as the SEC asks callers to do. That value is sent as the User-Agent header and is not printed, logged, or cached. A company is included only when its normalized name is an exact match in the SEC ticker file. A miss means no EDGAR facts for that company.

Public records do not contain a personal email, a private phone number, a consent flag, or the scoring attributes on a profile. SAM point-of-contact phone and email are not public, so they are not copied. The Phoenix permit layer used here does not publish a project value, so that field stays blank. A record with no email can still be drafted and approved. The approval screen lists the channels the record does have, and the outbox file says "No email on record". The existing score and exclusion rules still decide whether a draft is allowed.

Offline mode replays small fixture files shaped like the live responses and makes no network call. If one source times out or is rate limited, the page shows one sentence naming that source and keeps the records from the others.

## Live mode

Live mode calls three vendors. The Tailor uses Google (`gemini-4-argon`). The Drafter uses Anthropic (`claude-fable-5-2`). The Evaluator uses OpenAI (`gpt-6.2-astra`). If `LEADGEN_LLM_MODE` is unset, the mode is live.

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

Set `LEADGEN_DEMO_TEMPT=1` to add one visible line to the Drafter on attempt 1: "mention an introductory discount." The flight recorder marks those calls with `red_team` true. Attempt 2 does not get the line. Leave the variable unset for a normal search.

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
- Allowlist only is on by default. Send now then reaches only an address or domain in `allowlist` in `config/pipeline.yaml`, or the signed-in account's own address. Any other address can still be saved as a draft. Turning Allowlist only off is a Settings switch, and the page warns you.
- One note can be sent once. A later draft of that same note is still allowed.
- Send now stops after `send_cap` messages in the session. The default is 5.
- Every message keeps the sender identity and the opt-out line the verifier already required.
- The kill switch blocks drafting and sending.
- A failed sign-in, a network failure, or a provider rejection shows one plain message and a Reconnect button. The note is not marked sent unless the provider returns a message id. Settings shows each account as Connected with the address, Not connected, or Expired.

## Live copy

- URL: `https://<custom-name>.streamlit.app` (placeholder until the app is deployed).
- Redeploy: push to `main`. Cloud rebuilds. If the old look shows, Manage app, three-dot menu, Reboot.
- Secrets: only in the Streamlit Secrets box, never in the repo. Names: `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LEADGEN_LLM_MODE = "live"`. Type straight quotes.
- Cloud-only differences: Gmail and Outlook are hidden; an approved note gets "Copy email" and "Open in my email app"; searches and drafts reset when the app restarts; "Check keys" is hidden.
- The link is open (no password) by decision. See `DECISIONS.md`.

## Architecture

```
on-screen fields (translator only when the request box has text) → public-record sources (code) → de-dup, suppression, rank (code) → reason line (AI, checked) → shortlist → Intake → Exclusions → Qualify (code) → Tailor (AI, approved claims only) → Draft (AI, {{tokens}}) → Verifier (code) → Blind evaluator (AI) → one capped revise → Human approval → outbox/ (Practice) or Gmail/Outlook draft or send → Funnel metrics (code); every step → runs/flight_recorder.jsonl
```

The scout (scoring code) decides who is worth a call. The copywriter (AI) writes from an approved fact sheet. The compliance desk (verifier) sends sloppy copy back. A tough customer (blind evaluator) says whether it would get read. The sales manager (a person) signs before anything leaves.

## Governance

**Owner:** Dr. Michael Seller (AI Alchemy)

NetWitness exposure questions:

**What can it do?**
It reads synthetic prospect files and profile YAML, scores them, and, for people who clear the bar, drafts a message from approved claims. Code checks that draft. A blind reader scores it. A person approves it. Approval writes a file under `outbox/`. After that approval, the signed-in user can save the note as a draft in their own Gmail or Outlook account, or send it from that account. Practice does not email anyone. The repo has no SMTP library.

**What can it reach?**
Local files in this project: `config/`, `sample_data/`, `runs/`, and `outbox/`. Keys are read from `C:\Users\msell\secrets\` when that file exists, and are not stored here. Offline mode opens no network connection for the draft. Live mode calls Google, Anthropic, and OpenAI for the draft, and, when Search runs, SAM.gov, SEC EDGAR, the City of Phoenix permit service, and the Census Bureau County Business Patterns API. When you connect a mailbox, it can also reach your Gmail or Outlook account to create a draft and to send. The Outlook permission `Mail.ReadWrite` technically allows reading mail, because Graph requires it to create a draft. The code never lists or reads messages. It does not reach a CRM or a customer database. Sample prospects are fictional `@example.com` addresses. Search results are public records and are not copied into the repo.

**What evidence remains?**
Each step appends one line to `runs/flight_recorder.jsonl`. A mailbox draft or send adds a line with the destination, account, recipient, provider message id, approver, and result. The body and the tokens are not in that line. A run also keeps its tailor result, draft, rendered message, verification, evaluation, and status under `runs/<prospect-id>-<UTC timestamp>/`. A confirmed mailbox action adds `mail.json` there. `outbox/` holds the Practice copy. Sample data and tests stay in the repo. `.env` is not committed. `runs/` and `outbox/` are gitignored except for their `.gitkeep` files.

**Kill switch:** set `LEADGEN_KILL_SWITCH=1` in `.env`, or create a file named `KILL_SWITCH` in the repo root. The pipeline refuses to run. Only the value `1` turns the env switch on. If `LEADGEN_KILL_SWITCH` is already set in the process environment, the value in `.env` does not replace it.

The compliance checks are rules in this tool. They are not legal advice.
