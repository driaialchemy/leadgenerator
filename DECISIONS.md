# Decisions

## 2026-11-18 — Stack

Python 3.11, Streamlit, and Pydantic v2. PyYAML for profiles and the pipeline file. pytest for tests. Streamlit and the Anthropic client are listed now and unused until later milestones.

## 2026-11-18 — Domain profiles in YAML

Scoring rules, approved claims, subject lines, banned phrases, and sender identity live in `config/profiles/*.yaml`. The Python package does not name an industry or a profile id. `validate_samples` discovers profiles by listing `config/profiles/*.yaml`.

## 2026-11-18 — Deterministic scoring and exclusions

Scoring and exclusion rules are stored in this milestone and applied in code in M2. The model does not decide who is worth a draft.

Tier labels: hot is score ≥ `hot_min`, warm is `warm_min` through `hot_min - 1`, cold is below `warm_min`. `draft_threshold` is a separate gate. A score of 60 is warm and draftable. A score of 50 is warm and is not drafted.

The pipeline file is rejected unless `0 <= warm_min < hot_min <= 100` and `0 <= draft_threshold <= 100`. `consent_status_is` is a list of consent values (the sample file uses `["none"]`). `do_not_contact_is` is a bool.

## 2026-11-18 — AI selects approved claims by ID

The tailor step (M3) picks claim ids from the profile. It does not write claim text. Prospect facts appear only as `{{tokens}}` rendered by code.

## 2026-11-18 — Code-only verifier

`src/leadgen/verifier.py` stays deterministic Python. It does not import an AI or network library. The same rule covers `scoring.py` and `metrics.py`.

## 2026-11-18 — Blind evaluator

A skeptical-buyer rubric (M3) sees only the rendered email, not the score or the rationale. One capped revision runs if the verifier or the evaluator fails.

## 2026-11-18 — Simulated send

No module imports smtplib or any email/SMS-sending library. "Send" means writing a file under `outbox/`.

## 2026-11-18 — Append-only flight recorder

`runs/flight_recorder.jsonl` is append-only (M3). Writes are single-threaded.

## 2026-11-18 — Synthetic data only

Sample prospects and outcomes are fictional. Email addresses end in `@example.com`. No customer data.

## 2026-11-18 — Compliance checks are demo rules

Banned phrases, consent flags, and the opt-out line are teaching rules. They are not legal advice.

## 2026-11-18 — Scoring-rule allowlist

A `range` rule may name `last_engaged_days` or an `int` attribute. An `in` rule may name `source`, `consent_status`, `region`, or a `str` attribute. Anything else is rejected. `min` and `max` are inclusive and are stored, not applied, in M1. A range rule with neither `min` nor `max` is rejected.

## 2026-11-18 — YAML value `none` is quoted

In YAML 1.1 the bare word `none` is null. Profile values and `consent_status_is` quote it so it stays the string `none`.

## 2026-11-18 — Editable install from src/

`requirements.txt` ends with `-e .`. `src/leadgen/__init__.py` is empty so `python -m leadgen.validate_samples` works. `*.egg-info/` is gitignored.

## 2026-11-18 — Kill switch reads .env without overriding the process

`python-dotenv` loads `.env` from the repo root, or from the `root` argument when `is_engaged` is given one. `override=False`, so a variable already set in the environment is left as-is. The switch is on when `LEADGEN_KILL_SWITCH` is `1` or a `KILL_SWITCH` file is present. The `.env` test changes directory into `tmp_path` and passes that directory as `root`, so it does not read the repo `.env`.

## 2026-11-18 — Shared repo_root()

`src/leadgen/paths.py` is one function. Profiles, loaders, the kill switch, and the sample validator use it.

## 2026-11-18 — Two Cursor rules

`governance.mdc` covers `verifier.py`, `scoring.py`, and `metrics.py`. `outbox.mdc` covers `outbox.py`. One rule file has one body. Neither file restates `AGENTS.md`.

## 2026-11-18 — Fictional senders

Copperline: Morgan Ellis, 100 Example Way, Phoenix, AZ 85000. Desert Peak: Avery Cole, 200 Example Way, Phoenix, AZ 85000. Both profiles share one opt-out sentence. The call to action is fixed text on the profile.

## 2026-11-18 — Outcome rows

Record ids and dates were not in the build prompt. They are frozen in the outcome CSV files. Stage mix, confirmed before those files were written:

- b2b_services: won 2 (18000, 24000), lost_after_meeting 1, meeting 1, replied 2, sent 2.
- home_services: won 3 (9500, 7200, 350), lost_after_meeting 1, meeting 0, replied 1, sent 3.

Blank `deal_value` cells are empty, not zero. Won totals are 42000 and 17050.

## 2026-11-19 — Exclusions before scoring

`apply_exclusions` runs first. A person is excluded when `do_not_contact` equals `do_not_contact_is`, or when `consent_status` is in `consent_status_is`. If both match, the reason is `do_not_contact`. One reason is kept. `qualify` does not build a `ScoreResult` for an excluded person.

## 2026-11-19 — Score trace

`rule_hits` lists every profile rule. `points` is that rule's weight. `matched` says whether this prospect earned it. The total is the sum of the matched weights. Range bounds are inclusive. Tier and `draft_eligible` come from `pipeline.yaml`. A score of 60 would be draftable. The tier labels stay separate from that gate.

## 2026-11-19 — Findings never block

Note checks fire on a case-insensitive phrase in the notes. `flag_when` is an inclusive extra test and requires a declared int attribute. A check that names an attribute and has no `flag_when` fires on the phrase alone. Findings go to the human. `passed` ignores them.

## 2026-11-19 — Renderer fills tokens

Code replaces `contact_first_name`, `organization`, `region`, and `sender_name`. Subject lines stay on the M1 allowlist (`organization` and `contact_first_name` only). Bullets use approved claim text in the draft's claim order. The footer is code, so the digit check does not read it.

## 2026-11-19 — Banned phrases

`phrases.py` is the one matcher. A phrase of letters and spaces matches whole words, so "freedom" does not trip "free". A phrase with any other character, such as `$` or `% off`, matches as a substring. Profile load uses the same function on claims, subjects, and the CTA.

## 2026-11-19 — Verifier

`verify` recomputes eligibility and raises `IneligibleProspect` for an excluded person or a score under the draft threshold. Blocking checks cover the AI-written hook and bridge, plus subject id, claim ids, and evidence. Each issue message names the offending text. `max_ai_words` is 90 and `max_claims` is 2. `max_ai_words` must be at least 10. `max_claims` must be at least 1.

## 2026-11-19 — Claim ids are a set

Tailor and draft `claim_ids` match when the sets are equal. Order does not matter, and a swap is not `claim_mismatch`. A repeated id in either list fails `claim_count`, as does a count outside 1 through `max_claims`. The renderer still prints claims in the draft's order.

## 2026-11-19 — Funnel

Every outcome counts as sent. Replied also includes meeting, won, and lost_after_meeting. Meeting also includes won and lost_after_meeting. Rates divide by sent. `avg_deal` is `won_value / won` rounded to two places. An empty list yields zeros and does not divide by zero.

## 2026-11-19 — Qualify prints only

`python -m leadgen.qualify` checks the kill switch, then prints the ranked table, exclusions, findings, and funnel. It writes no files.

## 2026-11-19 — Three vendors, keys outside the repo

The Tailor calls Google, the Drafter calls Anthropic, and the Evaluator calls OpenAI. Defaults live in code. `LEADGEN_<ROLE>_PROVIDER` and `LEADGEN_<ROLE>_MODEL` override them. No temperature and no thinking budget are set. Anthropic sends `max_tokens=4096` because that API requires a cap. Each call times out after 60 seconds.

The class default is live. Offline replay remains the test mode and the no-Wi-Fi backup. Keys load from the first existing file among `LEADGEN_ENV_FILE`, `C:\Users\msell\secrets\workuity.env`, and `C:\Users\msell\secrets\leadgenerator.env`. A missing key names the variable and does not construct a client. `LEADGEN_DEMO_TEMPT=1` adds one discount instruction to the Drafter on attempt 1 and logs `red_team` true.

## 2026-11-19 — Vendor failures stay one line

A quota, auth, missing-model, or timeout response raises `ProviderError` with the provider, model, HTTP status, and a one-line reason. Keys are scrubbed out of that reason. `leadgen.run` prints the role, provider, and reason, records an `error` event, and exits. `check_keys` prints the same reason after `call fail`. `ConfigError` remains the signal for a missing key or a bad setting.

The kill switch is checked before every model call and before approval.

Ineligible prospects are refused with a flight-recorder line and no run folder. Everyone else gets one run folder. The tailor gate checks claims and evidence by re-reading `tailor.json`. A failure there retries the tailor. A verifier or evaluator failure retries the drafter. The run has one retry. Compliance that is still failing is `BLOCKED`. Quality that is still under the bar is `PENDING_APPROVAL` with `evaluator_below_bar` true. The evaluator sees only the rendered message and `buyer_persona`. Code applies the bar. The model does not return pass or fail.

## 2026-11-19 — Approval writes a file, not an email

A named person chooses `APPROVED`, `EDITED`, or `REJECTED`. Findings must be acknowledged when any exist. The draft on disk is hashed at verification and checked again at approval. An edit is run through the same verifier. `REJECTED` writes nothing to `outbox/`. An accepted decision writes `outbox/<run_id>.txt` once, after the approval file is read back from disk. A second decision is refused.

## 2026-11-20 — Class page calls decide

`decide` holds the approval rules. `python -m leadgen.approve` prints the message `decide` returns, so the CLI lines stay the same. The Streamlit Review tab calls `decide` and shows that message on the page.

The page is layout only. `ui_data.py` shapes the ranked table, attempt comparison, logbook, and outbox list. `run_prospect` accepts an optional progress callback and still writes the same files. A model call happens only when Run is pressed. The red-team toggle sets `LEADGEN_DEMO_TEMPT` for that click only.

Runs and the outbox go to `LEADGEN_DATA_ROOT` when that variable is set, and to the repo root otherwise. Profiles, prompts, and sample files still come from the repo. Tests point the data root at a temp folder. The theme and the three processed photos live in this repo. Each photo is under 150 KB.

## 2026-11-20 — Public-record search

Search reads three public sources through one adapter shape: source name, source record id, source URL, and record date. The profile YAML names which sources to use and how fresh each one is. SAM.gov uses 400 days and its last-update date. Phoenix permits and EDGAR use 180 days.

SAM.gov is the Entity Management API, public sections only, with `SAM_API_KEY`. Responses cache under `runs/source_cache/` for 24 hours. The cache key and the file omit the API key. EDGAR matches `company_tickers.json` by exact normalized business name and does not guess. Phoenix uses the published ShapePHX permit points. That layer has no valuation, so value stays blank.

A stale record is a flag beside the main label. The label is Named contact, Business phone on record, or Mailing address only, and only when the record contains that channel. Records are de-duplicated on UEI, or on name plus address, before suppression and ranking. Suppression matches business name, domain, or UEI.

A prospect with no email still runs through the existing pipeline. The draft is verified as before. The approval screen shows the channels on the record. The outbox file adds the line "No email on record". Scoring, verifier, and approval rules are unchanged. The flight recorder adds `search`, `source_call`, and `add_to_pipeline`.

## 2026-11-20 — Three income-model profiles

`ai_automation_services`, `admin_assist_services`, and `newsletter_sponsorships` are YAML, sample CSVs, and offline replays. The pipeline, scoring, verifier, and approval code are unchanged. Each profile bans earnings language, including `$` and `%`, and flags a note that asks for a guaranteed result or an ROI. Approved claims describe the service. The admin claims say a person reviews the work.

Search for the first two is SAM.gov by NAICS `541511` and `561110`. The letter profile searches SAM.gov for Phoenix, AZ, with no NAICS. Freshness is 400 days.

`menu_order` defaults to 0. The new profiles set 1, so the picker still opens on the original profile. The Python names no profile id.

## 2026-11-20 — Class page a person can use

The screen is layout. Search, scoring, the verifier, and approval are unchanged. A widget key owns its value. The page sets that value in the button click, or before the widget is created, and it does not pass both a default and a key. An example writes the request into the box and runs the search. Update results calls `execute` with the edited fields and does not translate the sentence again.

The sidebar is the business and Practice data or Live. A red notice appears only when the kill switch is on. Check keys and the red-team toggle are on Settings. Check keys still does not show a key. The stored status file still says `PENDING_APPROVAL`. The page says "Waiting for your approval".

The theme is light. It lives in `.streamlit/config.toml` and `ui_theme.py`. Text on each surface meets a 4.5 contrast ratio. The page does not render an image, and the repo does not ship one. The earlier light-on-white inputs came from a light text color painted on the whole page, which the white inputs inherited.

## 2026-11-20 — Guided wizard

The class page is five steps: Find, Shortlist, Draft, Review, and Send. A step that is not ready stays put and says why. The current step has one primary button. Logbook, Funnel, and Settings stay in the main area and open from More, so Check keys and the red-team toggle are not sidebar widgets.

The counts are businesses found, the ranked shortlist, drafts still waiting, approved decisions, and outbox files. A run that already has `approval.json` is not counted as waiting. The stored status file is still `PENDING_APPROVAL`.

White text failed the 4.5 ratio on the bright teal, green, amber, and coral, so those fills are a darker shade of the same hue. The waiting chip keeps the bright amber and uses dark text. The current step, the primary button, and the disabled primary button set their own text color, so the page color does not cover them. Icons are inline SVG. The page still does not ship a picture.

## 2026-11-20 — Mailbox draft and send

Practice is still the outbox file written when a person approves. Gmail and Outlook are a later step, and only for a note that already has an approval record. The Gmail scope is `gmail.compose`. Graph uses delegated `Mail.Send` and `Mail.ReadWrite`. `Mail.ReadWrite` can read mail, because that is what Graph requires to create a draft. The client never lists or reads messages.

Save as draft is the default. Send now requires a second confirmation. Demo safety defaults on, for the session only, and blocks a send to anyone except the allowlist or the signed-in account's own address. A draft is still allowed. Each run can be sent once. The session cap defaults to 5. The kill switch blocks both. A prospect with no email is refused. Nothing is marked sent unless the provider returns a message id. The flight recorder stores the destination, account, recipient, message id, approver, and result, and does not store the body or a token. Client files and tokens stay in `C:\Users\msell\secrets`.

## 2026-11-21 — Industry match and county size totals

Find matches typed text to an official 2022 NAICS title with `difflib` and `config/naics_synonyms.yaml`. The person keeps chips. The request URL receives the code only. A NAICS code is allowed when it is in that official list, so a search can leave the profile's short list. `999999` and any other code that is not on the list are still dropped. Phoenix runs only when `config/permit_map.yaml` maps a chosen code to a permit type that profile already allows. Otherwise that source is skipped.

Size bands are the Census classes 1–49, 50–249, 250–499, and 500–999. A record with no headcount stays in the list unless "Only show businesses with a known size" is on. Nothing is estimated. SAM.gov's employee count is not public, EDGAR submissions have no headcount, and the Phoenix fields used here have none. Live mode says so and points to the Market size card.

The card reads County Business Patterns for 2023, the latest year the Census Bureau has published, for the county on the profile. The default is Maricopa County, Arizona. It shows establishment counts by industry and size band. Those are county totals, not businesses. `CENSUS_API_KEY` is optional and is not stored in the 24-hour cache. If the call fails, one plain sentence is shown and the business search still returns.
