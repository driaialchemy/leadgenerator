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
