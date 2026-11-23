# Handoff

## Current milestone

M11.1 done locally, not pushed. Search results are now businesses, not permit rows: names come from company fields or valid site names, irrelevant permits are left out and counted, repeat businesses collapse to one row, a contact shows only for a real person's name, and the score spreads 44 to 76 on live data. The translator parses live replies. M10, M11, M12, and M11.1 are local commits on top of `origin/main`. The public repo is https://github.com/driaialchemy/leadgenerator.

## Done

- M1 scaffold and M2 scoring, findings, renderer, verifier, and funnel.
- Three vendors: Tailor on Google, Drafter on Anthropic, Evaluator on OpenAI. Live is the class default. Tests force offline and never open the real key file.
- One retry per run. A tailor-gate failure retries the tailor. A verifier or evaluator failure retries the drafter. B2B-001 and HOME-002 block on attempt 1 and pass on attempt 2. B2B-002 fails specificity once, then passes. B2B-004, HOME-001, and HOME-004 pass on the first attempt with the same findings as M2.
- B2B-003 and B2B-005 are refused. No run folder and no model call.
- `runs/flight_recorder.jsonl` is append-only. Retries record `attempt_number`, `retry_of`, and `retry_reason`.
- `python -m leadgen.check_keys` reports each provider without printing a key. `LEADGEN_DEMO_TEMPT=1` tempts the Drafter on attempt 1 only.
- Approval writes `outbox/<run_id>.txt` once. `REJECTED` writes nothing. The kill switch stops run and approve before a model call. The page calls `decide`, the same function the CLI prints.
- Replays live in `sample_data/replays/`. B2B-001 and HOME-002 reuse the caught fixture, then the good fixture.
- The page is `src/leadgen/app.py`. Launch it with `powershell -ExecutionPolicy Bypass -File run_app.ps1`. The steps are Find, Shortlist, Draft, Review, and Send. The sidebar is the business name and More. More holds the logbook, the funnel, and Settings. Settings holds the model for each step, Check keys, Allowlist only, and the Gmail and Outlook connection. The page says "Waiting for your approval" and does not ship an image.
- Send offers Practice, Gmail, and Outlook. Practice is the outbox file written at approval. Gmail uses the compose scope. Outlook uses delegated `Mail.Send` and `Mail.ReadWrite`. The code never lists or reads messages. Tokens stay in `C:\Users\msell\secrets`. See `docs/EMAIL_SETUP.md`.
- Mail safeguards live in `deliver`: an approval record, a second confirmation, Demo safety, the signed-in address on the allowlist, one confirmed send per run, a session send cap, no email means no mailbox action, the opt-out line and sender identity, and the kill switch. A provider must return a message id before the note is marked sent.
- Search reads SAM.gov in live mode. Offline replays trimmed fixtures. The live profile no longer enables SEC EDGAR or city permit feeds.
- Find matches a typed industry to a 2022 NAICS title, including a misspelling, and shows removable chips. Size bands are 1–49, 50–249, 250–499, and 500–999. The typed words are not sent. SAM, EDGAR, and Phoenix do not provide a public headcount, so those rows say "Size not in public record".
- The Market size card reads County Business Patterns for 2023, the latest published year, for the profile county (Maricopa County, Arizona by default). It shows establishment counts by size band. It is county totals, not a list of businesses. `CENSUS_API_KEY` is optional. A census failure is one plain sentence and the business search still returns.
- Acme Plumbing is the only profile in `config/profiles/`. Sender name, postal address, and phone are placeholders. Gmail and Outlook Send now is refused until those three are real. Drafts and Practice still work. The approved price is "$150 per hour plus parts". A discount or a different price is blocked.
- Search uses the on-screen fields. The translator runs only when the request box has text. A bad model reply is ignored after one retry and the field search still runs. Unknown extra JSON keys are dropped. NAICS codes are still checked against the CSV, and the other values are still checked against the fixed lists.
- Search no longer pre-fills or offers profile example queries. The Find page distinguishes Offline saved example records from Live public-record searches and explains that the LLM translates optional request text into filters.
- `run_app.ps1` now sets `LEADGEN_LLM_MODE=live` by default; an explicit environment setting of `offline` is still honored for demonstrations.
- Find has an explicit option to include businesses without a named contact. A target industry must be selected from a fuzzy NAICS match; only rows carrying a selected NAICS code are returned. Results show at most 25 businesses per page. Repeating the same search refreshes source data and advances to unseen results where available. Source-level diagnostics are kept off the results page.
- SAM.gov is one Arizona query. Metro cities are filtered in code. `sam_page_budget` defaults to 5. A rate limit or daily limit stops SAM and keeps fetched rows. The record cap is 200.
- The shortlist is `runs/shortlist.json`. It shows the businesses added from Find, by name. Scoring rewards selected-industry match, a named contact, and the configured service area.
- 171 passed, 2 skipped. Those 2 run only when `LEADGEN_LIVE_TESTS=1`. Mail tests use fake Gmail and Graph clients.
- Published on `main` at https://github.com/driaialchemy/leadgenerator. M10 and M11 are local commits on top of that.

## Next

M10, M11, M12, and M11.1 are committed locally. Push when the owner replies "approved push". M6 through M9 are already on main. M10 is the commit under M11 and is also unpushed.

- Hero photo: Mike supplies `assets/source/hero_shower.jpg` (git-ignored). Until it exists the hero is a blue-to-cyan gradient with a water drop. The first render with a photo writes `assets/hero_shower_web.jpg`, under 150 KB, and reuses it.

## Known issues

- No hero photo is in the repo yet, so the gradient shows.
- Live company search requires `SAM_API_KEY`. If it is unavailable, the Find page shows one short availability message and omits source-level setup diagnostics. Keys are read on every search, so a restart is not needed.
- Old runs from removed profiles are still in `runs/` and `outbox/`. The tiles skip them.

## 2026-11-21 — AI Lead Finder class feedback

- The visible profile name and hero title are now AI Lead Finder. The old profile file/id stays in place for compatibility with existing fixtures and stored data. Its sender details remain placeholders; do not send until the owner configures a real sender identity.
- The permit search no longer filters on a single trade. Empty permit criteria keep public permit records that have a usable business name. Search status text is general. The Arizona public-source coverage and missing SAM.gov / SEC EDGAR credentials are still real limitations; never imply those sources are active when they are not.
- Each `run_app.ps1` launch gets a new session root under `%LOCALAPPDATA%\AI Lead Finder\sessions\<timestamp>`, so the activity tiles start at zero without removing historical runs or outbox files. The kill switch still checks the repository and session root.
- Find distinguishes the sender's occupation/service field from the target company industry selected using official industry suggestions. Both are stored with a shortlist prospect and passed to the tailor and drafter as targeting context; the writer must not invent recipient needs or facts.
- Funnel is removed from the page navigation and panels. Internal metrics and CLI support remain unused by the app.
- `python -m leadgen.validate_samples` passed. Tests were not run in this update.

## 2026-11-21 — NAICS search and result paging

- Target-company search is now NAICS-driven. The picker accepts exact numeric NAICS codes and fuzzy industry names, including the supplied computer-parts, auto-parts, and social-media-marketing examples. Non-confident broad sector suggestions are not selectable.
- Only SAM.gov is enabled for live company results. SEC EDGAR and the Phoenix/Tucson permit feeds are removed from the profile, eliminating their setup and permit-filter messages from Find. Search requires a selected NAICS match and filters out records without a matching NAICS code.
- The Find page displays a maximum of 25 results per page. “Next 25 results” and “Previous 25” page through fetched matches. Running the same search again forces a fresh SAM request and advances to unseen matches where available; when none remain, the page says so.
- The current key file still lacks `SAM_API_KEY`, so live company records cannot appear until that source is configured. Its raw key/setup message is no longer shown on the results page.
- The sender occupation/service field is unrestricted free text. It is not limited to the sample NAICS synonym examples and can guide writing from any role the user enters.
- `python -m compileall -q src/leadgen`, `python -m leadgen.validate_samples`, and manual fuzzy-match checks passed. Tests were not run.

## 2026-11-21 — NAICS suggestions and legacy SIC

- Replaced the 48-row partial industry catalog with the U.S. Census Bureau 2022 NAICS structure (2,122 entries). The picker now ranks lexical near matches and only presents relevant candidates; the user selects the final code. Fitness clubs, fitness center, gym, and NAICS 713940 resolve to “Fitness and Recreational Sports Centers”.
- After selecting NAICS 713940, Find displays the associated legacy SEC SIC choice, 7991 (Physical Fitness Facilities). This is a historical classification; live company search continues to use selected NAICS codes.
- `python -m leadgen.validate_samples` passes. The full existing suite currently reports 24 failures and 179 passes, 2 skips, including failures unrelated to this matching change; tests were not edited. See current test output before treating the project suite as green.

## 2026-11-21 — Search selection feedback

- The suggestion list collapses after selection while preserving the entered phrase. Find displays the selected NAICS code as the search criterion; the existing search callback passes that chosen code to the search function.
- Removed Census change-indicator `T` suffixes from NAICS titles. A selected NAICS now reveals its related legacy SIC selector when a mapping exists; common real-estate entries and fitness centers are mapped. Otherwise the page explains that no crosswalk entry is available.
- Changed the otherwise empty Streamlit header band to the page surface color to remove the dark strip shown in class screenshots.
- Verified with an AppTest callback smoke check: selecting “fitness clubs” stores NAICS 713940, enables Search, and renders the SIC selector. Focused matcher test and sample validation pass. Live rows still require configured SAM.gov access.

## 2026-11-22 — Live copy on Streamlit Community Cloud (M15)

- Pushed to `main` at `0dcbbc7`: the directory app, the dark neon look, the guide, and the Cloud changes. `pytest -q`: 212 passed, 2 live skips.
- Live URL: `https://<custom-name>.streamlit.app` (fill in after Mike deploys; planned name `aileadfinder-aialchemy`).
- Redeploy: push to `main`. Cloud rebuilds on its own. If the old look shows, Manage app, then the three-dot menu, then Reboot.
- Secrets live only in the app's Secrets box (Manage app, Settings, Secrets). Keys: `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LEADGEN_LLM_MODE = "live"`. Use straight quotes. Never commit them.
- Proved from a fresh clone: clean Python 3.11 venv install, Cloud flag, keys as environment variables only, one live draft approved. The Linux install was checked with `pip download --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:`, not run on Linux.
- The "Sent" tile counts approved notes in `outbox/`. On Cloud nothing is sent from the server, so read it as "approved".
