# M1 Plan — Lead & Income Generation Workflow scaffold

Status: **approved and built** (2026-11-18). Review adjustments: outcome stage mix confirmed before the CSV files were written; a range rule with neither min nor max is rejected; `consent_status_is` is a list; pipeline config must satisfy `0 <= warm_min < hot_min <= 100` and `0 <= draft_threshold <= 100`; `validate_samples` discovers `config/profiles/*.yaml`; the `.env` kill-switch test `chdir`s into `tmp_path`.

The `leadgenerator/` folder is empty. This plan follows the approved Track 1 (`capex`) M1 shape: one readable module per job, pytest with `pythonpath = ["src"]`, an editable install so `python -m leadgen.validate_samples` works, and a kill switch that reads `.env` without overriding an existing environment variable.

## Goal

Lay the rails for a teaching demo whose lesson is: code decides who to contact, the AI writes only from an approved fact sheet, code inspects every draft, and a human signs before anything leaves.

Milestone 1 creates the project scaffold, governance files, two domain profiles, synthetic prospects and past outcomes, Pydantic schemas, profile-aware loaders, a kill switch, and tests. A novice should be able to read every module aloud in a workshop.

The Python package never names an industry. Swapping the profile YAML is what changes the industry. No AI calls, no scoring math, and no email rendering in this milestone.

Done when `pytest -q` and `python -m leadgen.validate_samples` pass from the repo root, and `HANDOFF.md` records M1 done / M2 next.

## Files (full tree)

```
leadgenerator/
  M1-PLAN.md                              # this plan (kept as the approval record)
  AGENTS.md                               # rules every coding agent inherits
  CLAUDE.md                               # one line: Read and follow AGENTS.md.
  HANDOFF.md                              # milestone status; updated at the end of M1
  DECISIONS.md                            # dated decision log
  README.md                               # plain-English overview, setup, architecture, governance
  .env.example
  .gitignore
  requirements.txt
  pyproject.toml
  .cursor/rules/governance.mdc            # verifier.py, scoring.py, metrics.py
  .cursor/rules/outbox.mdc                # outbox.py only
  config/pipeline.yaml
  config/profiles/b2b_services.yaml
  config/profiles/home_services.yaml
  sample_data/b2b_services/prospects.csv
  sample_data/b2b_services/outcomes.csv
  sample_data/home_services/prospects.csv
  sample_data/home_services/outcomes.csv
  runs/.gitkeep
  outbox/.gitkeep
  src/leadgen/__init__.py                 # empty; required so `python -m leadgen...` works
  src/leadgen/paths.py                    # repo_root() only
  src/leadgen/schemas.py
  src/leadgen/profiles.py
  src/leadgen/loaders.py
  src/leadgen/kill_switch.py
  src/leadgen/validate_samples.py
  tests/test_schemas.py
  tests/test_profiles.py
  tests/test_sample_data.py
  tests/test_domain_agnostic.py
  tests/test_kill_switch.py
```

Not created in M1: `scoring.py`, `verifier.py`, `metrics.py`, `outbox.py`, tailor/draft/evaluator agents, flight recorder, approval gate, Streamlit UI. The Cursor rules still name those future files so the rules are in force when later milestones add them.

`src/leadgen/paths.py` is one function, `repo_root()`, that walks up from the file to the directory containing `pyproject.toml`. Profiles, loaders, the kill switch, and the sample validator all need that directory. One shared function keeps them from each growing a private copy.

### How each piece behaves

**Governance docs**

- `AGENTS.md` states the project purpose, the `src/` layout, and the probabilistic/deterministic boundary. It includes these rules in substance: the AI never writes facts, prices, or claims — prospect facts appear only as `{{tokens}}` rendered by code, and claims are selected by ID from the profile's approved list; `src/leadgen/verifier.py`, `scoring.py`, and `metrics.py` may not import `anthropic`, `requests`, `httpx`, or any network/AI library; no module may import `smtplib` or any email/SMS-sending library; "send" means writing a file to `outbox/`; industry-specific content lives only in `config/profiles/*.yaml`; file and record writes are single-threaded; synthetic data only, never real contacts; never commit `.env`; don't modify tests to make them pass; how to run tests.
- `CLAUDE.md` is one line: `Read and follow AGENTS.md.`
- `DECISIONS.md` is seeded, dated 2026-11-18, with: Python/Streamlit/Pydantic stack; domain profiles in YAML; deterministic scoring and exclusions; AI selects approved claims by ID; code-only verifier; blind evaluator (A4) instead of debate; simulated send to `outbox/` only; append-only `.jsonl` flight recorder; synthetic data only; compliance checks are demo rules, not legal advice. Any extra M1 choice below is appended when the code is written.
- `HANDOFF.md` starts as "M1 in progress" and is rewritten at the end to "M1 done, M2 next" with known issues (none expected).
- `README.md` is plain English: what the app is, one-command setup and test run, the architecture line below, and a Governance section. That section names Dr. Michael Seller (AI Alchemy) as owner, answers the three NetWitness exposure questions, documents the kill switch, and states that the compliance checks are illustrative demo rules, not legal advice.

Architecture line in the README:

```
prospects.csv → Intake → Exclusions → Qualify (code) → Tailor (AI, approved claims only) → Draft (AI, {{tokens}}) → Verifier (code) → Blind evaluator (AI) → one capped revise → Human approval → outbox/ (no real send) → Funnel metrics (code); every step → runs/flight_recorder.jsonl
```

Governance answers to write:

- **What can it do?** Read synthetic prospect files and profile YAML, check that they match the schemas, and (in later milestones) score, draft, verify, and write approved emails as files under `outbox/`. It cannot send email or SMS. The repo has no SMTP library.
- **What can it reach?** Local files in this repo (`config/`, `sample_data/`, `runs/`, `outbox/`). A later milestone can call the Anthropic API when a key is set and the mode is not offline. It does not reach a CRM, a mailbox, or a customer database. Contacts are fictional `@example.com` addresses.
- **What evidence remains?** Later milestones append every step to `runs/flight_recorder.jsonl`. `outbox/` holds the files that stand in for sending. Sample data and tests stay in the repo. `.env` is not committed.
- **Kill switch.** Set `LEADGEN_KILL_SWITCH=1` in `.env`, or create a file named `KILL_SWITCH` in the repo root. The pipeline refuses to run.

- `.cursor/rules/governance.mdc` is Cursor-only and file-scoped. Frontmatter: `alwaysApply: false`, globs `src/leadgen/verifier.py`, `src/leadgen/scoring.py`, `src/leadgen/metrics.py`. Body is only: "No AI or network imports; pure deterministic Python."
- `.cursor/rules/outbox.mdc` is a second file-scoped rule. Glob: `src/leadgen/outbox.py`. Body is only: "Writes files under outbox/ only; no smtplib, email-sending, or network libraries." One `.mdc` file has one body, so the two sentences live in two files. Neither file restates `AGENTS.md`.

**Config and env**

- `.env.example`:

```
ANTHROPIC_API_KEY=
LEADGEN_MODEL=
LEADGEN_LLM_MODE=offline
LEADGEN_KILL_SWITCH=0
LEADGEN_PROFILE=b2b_services
```

- `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `runs/*` with `!runs/.gitkeep`, `outbox/*` with `!outbox/.gitkeep`, `assets/source/`, and `*.egg-info/` (the editable install writes `src/leadgen.egg-info/`).
- `requirements.txt`: `pydantic>=2`, `PyYAML`, `pytest`, `streamlit`, `anthropic`, `python-dotenv`, then `-e .`. Streamlit and anthropic are installed and unused until M3/M4. `-e .` is what makes `python -m leadgen.validate_samples` work after the specified smoke command, because the package lives under `src/` and that command does not set `PYTHONPATH`.
- `pyproject.toml`: package name `leadgen`, requires Python `>=3.11`, setuptools build backend, packages found under `src`, pytest `pythonpath = ["src"]` and `testpaths = ["tests"]`. Dependencies stay in `requirements.txt`.

**Pipeline config** (`config/pipeline.yaml`)

Stored and validated. Not applied to prospects in M1.

```yaml
draft_threshold: 60
tiers:
  hot_min: 70
  warm_min: 40
max_revisions: 1
evaluator_pass_score: 4
exclusions:
  do_not_contact_is: true
  consent_status_is:
    - "none"
```

Tier meaning, for M2, written as comments in the YAML and in `DECISIONS.md`: hot is score ≥ 70, warm is 40 through 69, cold is below 40. `draft_threshold` is a separate gate (draft at 60 or above). A score of 60 is warm and draftable. A score of 50 is warm and is not drafted. Exclusions, when M2 applies them, are: `do_not_contact` is true, or `consent_status` is one of the `consent_status_is` values (`none` in the sample). The word `none` is quoted so YAML keeps it a string. `evaluator_pass_score` is 4 on a 1–5 rubric. `max_revisions` is 1.

`load_pipeline_config(path=None) -> PipelineConfig` reads that file. The model rejects unknown keys. It rejects a file unless `0 <= warm_min < hot_min <= 100` and `0 <= draft_threshold <= 100`. It also rejects `max_revisions` < 0 and an `evaluator_pass_score` outside 1–5. That is a shape check, not scoring.

**Profiles**

Each file is `config/profiles/<profile_id>.yaml`. `load_profile(profile_id, path=None) -> Profile` reads it. `path` lets tests point at `tmp_path`. The `profile_id` inside the file must match the argument.

Pydantic models use `extra="forbid"`. The YAML key `type` on a scoring rule maps to the field `rule_type` via an alias, so the file stays readable and the Python name does not fight the builtin.

A scoring rule is either:

- `type: range`, with optional `min` and `max` (at least one required; both inclusive; if both, `min` ≤ `max`), and `points`
- `type: in`, with a non-empty `values` list, and `points`

`points` are integers ≥ 0. Across the rules they must sum to exactly 100.

A rule field is allowed when it is one of these core fields, or a declared attribute of the matching kind:

| Rule type | Core fields | Declared attribute |
|---|---|---|
| `range` | `last_engaged_days` | type `int` |
| `in` | `source`, `consent_status`, `region` | type `str` |

A range rule on a string, or an `in` rule on an int, is rejected. M1 stores the bounds. It does not score anyone.

Approved claims and approved subjects are YAML mappings of id → text. Mapping keys are unique by the time Python sees them (PyYAML keeps the last duplicate key; M1 does not add a custom YAML parser). Subject text may contain only the tokens `{{organization}}` and `{{contact_first_name}}`. A subject may contain neither. Any other `{{...}}` token is rejected.

Sender, opt-out line, and call to action are fixed profile text. They are fictional. They avoid the banned phrases, including as substrings (`free`, `$`, and the rest).

`b2b_services` — display name "Copperline IT Services":

- sender: Morgan Ellis, Copperline IT Services, `100 Example Way, Phoenix, AZ 85000`
- opt_out_line: `If you would rather not hear from us, reply stop and we will remove you.`
- cta: `Reply with a time this week for a 15-minute call.`
- attributes: `employee_count` int, `industry` str, `current_it_setup` str
- scoring rules (sum 100):
  - `employee_count` range min 10 max 200 → 30
  - `industry` in dental, legal, accounting, medical_clinic → 25
  - `current_it_setup` in none, in_house → 15
  - `source` in referral, web_form → 20
  - `last_engaged_days` range max 30 → 10
- claims: VP-B2B-01 "24/7 monitoring and a live help desk"; VP-B2B-02 "Daily backups with quarterly restore tests"; VP-B2B-03 "A named account lead who knows your office"; VP-B2B-04 "Security awareness training for your staff"
- subjects: SUB-B2B-01 "A question about IT support at {{organization}}"; SUB-B2B-02 "Backups and security for {{organization}}"
- banned phrases: discount, `% off`, free, guarantee, risk-free, limited time, act now, `$`, `Re:`, `Fwd:`

`home_services` — display name "Desert Peak Heating & Cooling":

- sender: Avery Cole, Desert Peak Heating & Cooling, `200 Example Way, Phoenix, AZ 85000`
- opt_out_line: same sentence as the b2b profile
- cta: `Reply with a time this week for a system evaluation.`
- attributes: `property_type` str, `home_age_years` int, `system_age_years` int
- scoring rules (sum 100):
  - `system_age_years` range min 12 → 35
  - `property_type` in single_family, townhome → 15
  - `home_age_years` range min 15 → 10
  - `source` in referral, web_form → 25
  - `last_engaged_days` range max 14 → 15
- claims: VP-HOME-01 "Same-week system evaluations"; VP-HOME-02 "A written repair-versus-replace comparison before any work"; VP-HOME-03 "Licensed, background-checked technicians"; VP-HOME-04 "Maintenance plans with seasonal tune-ups"
- subjects: SUB-HOME-01 "Your cooling system, {{contact_first_name}}"; SUB-HOME-02 "Following up on your HVAC question"
- banned phrases: the same list as `b2b_services`

These two addresses differ so a later demo can show that swapping the profile changes the footer. Both are fictional.

**Schemas** (`src/leadgen/schemas.py`)

`Prospect`

| Field | Rule |
|---|---|
| `prospect_id` | string |
| `profile_id` | string |
| `contact_name` | string |
| `organization` | string or null |
| `email` | string |
| `region` | string |
| `source` | `referral`, `web_form`, `event`, or `cold_list` |
| `last_engaged_days` | int ≥ 0 |
| `consent_status` | `opt_in`, `existing_relationship`, or `none` |
| `do_not_contact` | bool |
| `notes` | string |
| `attributes` | dict of string → int or string |

`Outcome`

| Field | Rule |
|---|---|
| `record_id` | string |
| `profile_id` | string |
| `sent_on` | date |
| `furthest_stage` | `sent`, `replied`, `meeting`, `won`, or `lost_after_meeting` |
| `deal_value` | required and > 0 when stage is `won`; otherwise null |

A won row with a missing or non-positive `deal_value` is rejected. Any other stage with a `deal_value` present is rejected.

`Profile`, `ScoringRule`, `Sender`, and `PipelineConfig` mirror the YAML above.

**Loaders** (`src/leadgen/loaders.py`)

`load_prospects(profile, path=None) -> list[Prospect]` reads `sample_data/<profile_id>/prospects.csv` under the repo root, or `path` when a test passes one.

Core columns, in this order: `prospect_id`, `profile_id`, `contact_name`, `organization`, `email`, `region`, `source`, `last_engaged_days`, `consent_status`, `do_not_contact`, `notes`. Every other column is an attribute. The attribute columns must be exactly the profile's declared attributes. An extra column is rejected. A missing declared attribute is rejected. Each row's `profile_id` must equal the profile being loaded. A blank `organization` becomes null.

Types are parsed in the loader, then handed to Pydantic as real Python values:

- `do_not_contact` accepts only `true` and `false` (any case)
- an `int` attribute must be a base-10 integer
- a `str` attribute is the stripped cell

`load_outcomes(profile, path=None) -> list[Outcome]` reads `sample_data/<profile_id>/outcomes.csv`. Columns: `record_id`, `profile_id`, `sent_on`, `furthest_stage`, `deal_value`. A blank `deal_value` becomes null. Dates are `YYYY-MM-DD`.

**Kill switch** (`src/leadgen/kill_switch.py`)

- `is_engaged(root=None) -> bool`. Loads `.env` from the repo root, or from `root` when given, with `override=False`. Engaged when `LEADGEN_KILL_SWITCH` is exactly `"1"`, or when a file named `KILL_SWITCH` exists in that same directory. `"0"`, empty, and unset are off.
- `assert_not_engaged(root=None)` raises `KillSwitchEngaged` (a `RuntimeError` subclass) when engaged.
- The optional `root` argument is how tests use `tmp_path` without touching the real repo.
- M1 does not create or delete the `KILL_SWITCH` file. Nothing in M1 calls `assert_not_engaged` except its test.

**Sample validator** (`src/leadgen/validate_samples.py`)

`python -m leadgen.validate_samples` discovers `config/profiles/*.yaml` (it does not hardcode profile ids, so the source stays free of industry names). For each profile it loads the profile, its prospects, and its outcomes, then loads `config/pipeline.yaml`. It prints one line per file: `PASS <path>` or `FAIL <path>: <reason>`, with paths relative to the repo root. Exit code 0 when all pass, 1 otherwise.

Expected order:

```
PASS config/profiles/b2b_services.yaml
PASS sample_data/b2b_services/prospects.csv
PASS sample_data/b2b_services/outcomes.csv
PASS config/profiles/home_services.yaml
PASS sample_data/home_services/prospects.csv
PASS sample_data/home_services/outcomes.csv
PASS config/pipeline.yaml
```

**Synthetic prospects**

Notes, names, regions, sources, engagement, consent, `do_not_contact`, and attribute values are copied from the build prompt. Emails were not specified; they are `first.last@example.com` as listed below. Organization is blank on every home-services row.

`sample_data/b2b_services/prospects.csv`

| prospect_id | contact_name | organization | email | region | source | days | consent | do_not_contact | employee_count | industry | current_it_setup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B2B-001 | Dana Whitfield | Mesa Ridge Dental | dana.whitfield@example.com | Mesa | referral | 12 | opt_in | false | 18 | dental | in_house |
| B2B-002 | Marcus Alder | Alder & Finch Law | marcus.alder@example.com | Phoenix | web_form | 45 | existing_relationship | false | 42 | legal | other_msp |
| B2B-003 | Priya Raman | Juniper Accounting Group | priya.raman@example.com | Chandler | event | 20 | opt_in | false | 9 | accounting | none |
| B2B-004 | Tom Okoye | Saltbush Logistics | tom.okoye@example.com | Tempe | referral | 5 | opt_in | false | 120 | logistics | in_house |
| B2B-005 | Elena Cruz | Cholla Medical Clinic | elena.cruz@example.com | Scottsdale | web_form | 3 | opt_in | true | 35 | medical_clinic | none |
| B2B-006 | Rick Haines | Ironwood Retail | rick.haines@example.com | Glendale | cold_list | 90 | existing_relationship | false | 250 | retail | other_msp |

Notes, exact text:

- B2B-001: `Office mgr Dana. Their 'IT guy' is the owner's nephew. Backups 'probably' run. Sister practice had a ransomware scare in Sept. Asked if we do intro pricing.`
- B2B-002: `Current MSP contract ends next spring. Unhappy w/ response times. Wants someone who answers the phone.`
- B2B-003: `Met at chamber mixer. Tax season is their crunch. Small team, using personal laptops.`
- B2B-004: `Said 'we're 300 people now after the merger.' Two IT staff overwhelmed. Wants help desk coverage.`
- B2B-005: `Asked to be removed from all outreach last month.`
- B2B-006: `Bought list. No contact history.`

`sample_data/home_services/prospects.csv` — `organization` blank, `profile_id` `home_services`.

| prospect_id | contact_name | email | region | source | days | consent | do_not_contact | property_type | home_age_years | system_age_years |
|---|---|---|---|---|---|---|---|---|---|---|
| HOME-001 | Luis Ramirez | luis.ramirez@example.com | Gilbert | referral | 7 | opt_in | false | single_family | 22 | 16 |
| HOME-002 | Grace Chen | grace.chen@example.com | Tempe | web_form | 10 | opt_in | false | condo | 8 | 13 |
| HOME-003 | Ada Okafor | ada.okafor@example.com | Phoenix | event | 40 | opt_in | false | townhome | 30 | 6 |
| HOME-004 | Raj Patel | raj.patel@example.com | Chandler | web_form | 21 | existing_relationship | false | single_family | 18 | 14 |
| HOME-005 | Minh Nguyen | minh.nguyen@example.com | Mesa | cold_list | 60 | none | false | single_family | 25 | 19 |
| HOME-006 | Jordan Brooks | jordan.brooks@example.com | Peoria | referral | 30 | opt_in | false | single_family | 12 | 11 |

Notes, exact text:

- HOME-001: `Neighbor referred. AC struggling in afternoons. Wants to know repair vs replace.`
- HOME-002: `Asked about financing. Mentioned 'a neighbor got $1,500 off a new unit.' Noisy compressor.`
- HOME-003: `Home show visitor. System is newish, curious about maintenance.`
- HOME-004: `Says the unit is 'brand new, installed last year.' Wants a tune-up quote.`
- HOME-005: `Purchased list. No consent on file.`
- HOME-006: `Friend of a past customer. No urgent issue.`

CSV cells that contain commas or apostrophes are quoted. Encoding is UTF-8.

**Synthetic outcomes**

The build prompt fixes the stage mix and the won dollars, not the record ids or dates. These rows are the contract M2's funnel test will read. `furthest_stage` is the furthest stage reached, so the mix below produces the M2 funnel counts (b2b: sent 8, replied 6, meeting 4, won 2, $42,000; home: sent 8, replied 5, meeting 4, won 3, $17,050). Blank `deal_value` cells are empty, not zero.

`sample_data/b2b_services/outcomes.csv`

| record_id | profile_id | sent_on | furthest_stage | deal_value |
|---|---|---|---|---|
| OUT-B2B-001 | b2b_services | 2026-01-15 | won | 18000 |
| OUT-B2B-002 | b2b_services | 2026-02-03 | won | 24000 |
| OUT-B2B-003 | b2b_services | 2026-02-20 | lost_after_meeting | |
| OUT-B2B-004 | b2b_services | 2026-03-04 | meeting | |
| OUT-B2B-005 | b2b_services | 2026-03-18 | replied | |
| OUT-B2B-006 | b2b_services | 2026-04-02 | replied | |
| OUT-B2B-007 | b2b_services | 2026-04-22 | sent | |
| OUT-B2B-008 | b2b_services | 2026-05-11 | sent | |

`sample_data/home_services/outcomes.csv`

| record_id | profile_id | sent_on | furthest_stage | deal_value |
|---|---|---|---|---|
| OUT-HOME-001 | home_services | 2026-01-10 | won | 9500 |
| OUT-HOME-002 | home_services | 2026-01-28 | won | 7200 |
| OUT-HOME-003 | home_services | 2026-02-14 | won | 350 |
| OUT-HOME-004 | home_services | 2026-03-01 | lost_after_meeting | |
| OUT-HOME-005 | home_services | 2026-03-19 | replied | |
| OUT-HOME-006 | home_services | 2026-04-07 | sent | |
| OUT-HOME-007 | home_services | 2026-04-25 | sent | |
| OUT-HOME-008 | home_services | 2026-05-16 | sent | |

Won totals: 18000 + 24000 = 42000, and 9500 + 7200 + 350 = 17050.

Hand check of the scores M2 will compute later, so the frozen CSV is the one the demo table expects. M1 does not compute these.

| Prospect | Score | Tier | Why the points land there |
|---|---|---|---|
| B2B-001 | 100 | hot | 30 + 25 + 15 + 20 + 10 |
| B2B-002 | 75 | hot | misses the IT-setup points and the 30-day recency points |
| B2B-003 | 50 | warm | 9 employees and an event source; below the draft threshold of 60 |
| B2B-004 | 75 | hot | logistics is outside the industry list; notes disagree with 120 employees |
| B2B-005 | would be 100 | excluded | `do_not_contact` is true |
| B2B-006 | 0 | cold | every rule misses |
| HOME-001 | 100 | hot | 35 + 15 + 10 + 25 + 15 |
| HOME-002 | 75 | hot | condo and a young home miss two rules |
| HOME-003 | 25 | cold | only townhome + home age |
| HOME-004 | 85 | hot | last contact is 21 days, past the 14-day rule; notes disagree with system age |
| HOME-005 | would be 60 | excluded | consent is `none` |
| HOME-006 | 40 | warm | referral only; below the draft threshold |

## Tests

If a test fails, fix the code, not the test.

`tests/test_schemas.py`

- A valid prospect loads.
- An unknown field is rejected.
- An invalid `consent_status` is rejected.
- A negative `last_engaged_days` is rejected.
- An Outcome marked `won` without `deal_value` is rejected.
- A non-won Outcome with a `deal_value` is rejected.

`tests/test_profiles.py`

- Both profiles load.
- Each profile's scoring points sum to 100.
- A profile whose points sum to 95 is rejected (`tmp_path` YAML, first rule's points reduced by 5).
- A rule naming an undeclared field is rejected (rename one rule's field to `favorite_color`).
- Claim IDs are unique and subject IDs are unique.
- Every approved subject uses only the tokens `{{organization}}` or `{{contact_first_name}}`.

`tests/test_sample_data.py`

- Each profile has six prospects with unique IDs.
- Every prospect's attributes match its profile's declared attributes and types.
- A prospect CSV with an undeclared extra column is rejected (`tmp_path`).
- Every email ends in `@example.com`.
- Each outcomes file has eight rows.
- Won deal values sum to 42000 (`b2b_services`) and 17050 (`home_services`).

`tests/test_domain_agnostic.py`

- No `.py` file under `src/leadgen/` contains any of these strings, compared case-insensitively: `dental`, `hvac`, `copperline`, `desert peak`, `home_services`, `b2b_services`.

`tests/test_kill_switch.py` (`tmp_path` and `monkeypatch` only; the test never writes a real `KILL_SWITCH` in the repo)

- Off by default.
- On when `LEADGEN_KILL_SWITCH=1`.
- On when a `KILL_SWITCH` file exists under `tmp_path`.
- On when a `.env` in `tmp_path` sets `LEADGEN_KILL_SWITCH=1`.
- A `.env` value does not override a variable that is already set (`LEADGEN_KILL_SWITCH=0` in the environment stays off).
- `assert_not_engaged` raises `KillSwitchEngaged` when on.

The two `.env` tests are included because the README tells the owner to set the switch in `.env`. They match the approved Track 1 kill switch.

**Smoke test** (PowerShell, from `leadgenerator/`):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; pytest -q; python -m leadgen.validate_samples
```

After the smoke test passes: update `HANDOFF.md` (M1 done, M2 next) and append any new decisions to `DECISIONS.md`. No git commands.

## Out of scope

Scoring math, exclusion logic applied to rows, email rendering, the verifier, funnel metrics, AI calls, the flight recorder, the approval gate, the Streamlit UI, and git commands. Those belong to M2–M5.

Also out of scope for M1, so they are not built "while we're here":

- Any function that turns a prospect into a score, a tier, or a draft/no-draft decision
- Creating `scoring.py`, `verifier.py`, `metrics.py`, or `outbox.py`
- A pipeline runner that calls the kill switch (the function exists and is tested; nothing invokes it yet)
- A custom YAML parser that rejects duplicate mapping keys
- Base classes, plugin registries, or a config framework beyond the YAML files and their loaders
- Changing the sample rows away from the tables in this plan

## Choices that need a yes

1. **Two Cursor rule files.** `governance.mdc` covers the three deterministic modules. `outbox.mdc` covers `outbox.py`. One rule file can carry only one body.
2. **Editable install and an empty `__init__.py`.** `requirements.txt` ends with `-e .`. This is what makes the given smoke command able to import `leadgen`. Same choice as Track 1.
3. **Kill switch reads `.env`.** `python-dotenv` loads it with `override=False`. Only the value `"1"` or a `KILL_SWITCH` file engages it. Tests include the `.env` cases Track 1 added after approval.
4. **`repo_root()` in `paths.py`.** One small function shared by the loaders, the kill switch, and the sample validator.
5. **`*.egg-info/` in `.gitignore`.** The editable install creates that folder. The rest of the ignore list matches the build prompt.
6. **Fictional sender lines.** Morgan Ellis at 100 Example Way for Copperline; Avery Cole at 200 Example Way for Desert Peak. Shared opt-out sentence. CTAs as written above. These strings were not in the build prompt.
7. **Emails and outcome rows.** `first.last@example.com`, and the sixteen outcome rows in the tables above (ids, 2026 dates, stage mix, and the two won-dollar totals).
8. **Scoring-rule allowlist.** Core range field: `last_engaged_days`. Core `in` fields: `source`, `consent_status`, `region`. Everything else must be a declared attribute of the matching type. Bounds are stored and not applied.
9. **Pipeline YAML shape.** `hot_min` / `warm_min`, plus `exclusions.do_not_contact_is` and `exclusions.consent_status_is`. Loaded and shape-checked. Not applied to rows.
