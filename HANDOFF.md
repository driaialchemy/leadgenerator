# Handoff

## Current milestone

M12 done locally, not pushed. The page has Acme's own look: a cyan top bar, a hero with a wordmark, and a blue, sky, and slate palette. The words in the bar and hero come from `brand:` in `config/profiles/acme_plumbing.yaml`. Colors live only in `src/leadgen/ui_theme.py` and `.streamlit/config.toml`. Screen only; search, sources, pipeline, scoring, verifier, approval, mail, and the recorder are untouched. M10 and M11 are also local commits. The public repo is https://github.com/driaialchemy/leadgenerator.

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
- Search reads SAM.gov, SEC EDGAR, and City of Phoenix permits. Offline replays trimmed fixtures. A source that fails does not stop the others.
- Find matches a typed industry to a 2022 NAICS title, including a misspelling, and shows removable chips. Size bands are 1–49, 50–249, 250–499, and 500–999. The typed words are not sent. SAM, EDGAR, and Phoenix do not provide a public headcount, so those rows say "Size not in public record".
- The Market size card reads County Business Patterns for 2023, the latest published year, for the profile county (Maricopa County, Arizona by default). It shows establishment counts by size band. It is county totals, not a list of businesses. `CENSUS_API_KEY` is optional. A census failure is one plain sentence and the business search still returns.
- Acme Plumbing is the only profile in `config/profiles/`. Sender name, postal address, and phone are placeholders. Gmail and Outlook Send now is refused until those three are real. Drafts and Practice still work. The approved price is "$150 per hour plus parts". A discount or a different price is blocked.
- Search uses the on-screen fields. The translator runs only when the request box has text. A bad model reply is ignored after one retry and the field search still runs. Unknown extra JSON keys are dropped. NAICS codes are still checked against the CSV, and the other values are still checked against the fixed lists.
- SAM.gov is one Arizona query. Metro cities are filtered in code. `sam_page_budget` defaults to 5. A rate limit or daily limit stops SAM, keeps the fetched rows, and the status line says "SAM.gov daily limit reached; results resume tomorrow". Phoenix and Tucson use the larger ArcGIS page sizes. The record cap is 200.
- The shortlist is `runs/shortlist.json`. It shows the businesses added from Find, by name. Scoring is 30 in the service area, 25 for a named contact, 25 for a recent permit, and 20 for an industry that tends to hire commercial plumbing.
- 171 passed, 2 skipped. Those 2 run only when `LEADGEN_LIVE_TESTS=1`. Mail tests use fake Gmail and Graph clients.
- Published on `main` at https://github.com/driaialchemy/leadgenerator. M10 and M11 are local commits on top of that.

## Next

M10, M11, and M12 are committed locally. Push when the owner replies "approved push". M6 through M9 are already on main. M10 is the commit under M11 and is also unpushed.

- Hero photo: Mike supplies `assets/source/hero_shower.jpg` (git-ignored). Until it exists the hero is a blue-to-cyan gradient with a water drop. The first render with a photo writes `assets/hero_shower_web.jpg`, under 150 KB, and reuses it.

## Known issues

- No hero photo is in the repo yet, so the gradient shows.
- Live search needs `SAM_API_KEY`, `LEADGEN_EDGAR_USER_AGENT`, and `CENSUS_API_KEY`. None is in the key file, so only the Phoenix and Tucson permit sources return rows.
- Permit sources give a permit or project name and a contractor contact, not a verified business. They carry no email.
- Old runs from removed profiles are still in `runs/` and `outbox/`. The tiles skip them.
