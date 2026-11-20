# M2 Plan — Scout, typesetter, compliance desk, scoreboard

Status: **approved and built** (2026-11-19). Claim ids are compared as sets. Duplicate claim ids fail `claim_count`. The renderer keeps the draft's order.

M1 is in place: profiles, sample prospects and outcomes, schemas, loaders, kill switch. Sample CSVs stay as they are. Industry words stay in the profile YAML. The M1 domain-agnostic test still applies to every new module.

## Goal

Make the "Do I Need an Agent?" answer concrete. The rules are fixed, so code does this work. The AI is not called.

- Exclusions run first. Then ICP scoring from the profile, with every point traceable to a rule. Then the tier and the draft threshold.
- Note checks flag facts a person should see (a price question, notes that contradict a field). They are shown. They never block.
- Code renders the email. The AI's text keeps `{{tokens}}`. Code fills names, approved claim text, the CTA, and the footer.
- The verifier is code-only. Each blocking check is a small named function whose message tells the writer what to fix. Those messages become the M3 retry reason.
- Funnel metrics are computed from past outcomes.
- Four hand-written fixture drafts are stored for M3's offline replays.

Done when `pytest -q`, `python -m leadgen.validate_samples`, and both `qualify` commands pass from the repo root, and `HANDOFF.md` records M2 done / M3 next.

## Files

```
leadgenerator/
  M2-PLAN.md                              # this plan
  AGENTS.md                               # extend the import ban to the new pure modules
  config/pipeline.yaml                    # add max_ai_words, max_claims
  config/profiles/b2b_services.yaml       # add note_checks
  config/profiles/home_services.yaml      # add note_checks
  .cursor/rules/governance.mdc            # add exclusions.py, findings.py, renderer.py, phrases.py
  src/leadgen/schemas.py                  # new models; pipeline and profile fields
  src/leadgen/profiles.py                 # note-check and banned-phrase validation
  src/leadgen/phrases.py                  # one banned-phrase matcher, shared
  src/leadgen/exclusions.py
  src/leadgen/scoring.py
  src/leadgen/findings.py
  src/leadgen/renderer.py
  src/leadgen/verifier.py
  src/leadgen/metrics.py
  src/leadgen/qualify.py
  tests/fixtures/drafts/b2b_001_good.json
  tests/fixtures/drafts/b2b_001_caught.json
  tests/fixtures/drafts/home_002_good.json
  tests/fixtures/drafts/home_002_caught.json
  tests/test_exclusions.py
  tests/test_scoring.py
  tests/test_findings.py
  tests/test_renderer.py
  tests/test_verifier.py
  tests/test_metrics.py
  tests/test_qualify.py
  tests/test_profiles.py                  # two additions
```

Not created: prompts, offline replays, flight recorder, approval gate, outbox writer, UI.

### Config

`config/pipeline.yaml` gains:

```yaml
max_ai_words: 90
max_claims: 2
```

`PipelineConfig` requires `max_ai_words >= 10` and `max_claims >= 1`. The existing bounds test gains two rejected cases: `max_ai_words: 9` and `max_claims: 0`. `test_pipeline_config_loads` also asserts the two new values.

Each profile gains `note_checks`. A check fires when any phrase is a case-insensitive substring of the notes. If `flag_when` is set, the named attribute must also fall inside that inclusive range. `flag_when` without `attribute` is rejected. An attribute, when set, must be a declared profile attribute. `flag_when` requires that attribute's type to be `int`. Check ids are unique inside the profile. Phrases and the message are non-empty. `flag_when` needs a min, a max, or both, and min cannot exceed max.

`b2b_services`:

```yaml
note_checks:
  - id: pricing_question
    phrases: [pricing, financing, quote, price]
    message: "Prospect asked about price. A person answers this; the AI may not quote."
  - id: headcount_change
    phrases: [merger, acquired, people now]
    attribute: employee_count
    message: "Notes suggest headcount changed. Confirm employee_count before relying on the score."
```

`headcount_change` names the field for the human. It has no `flag_when`, so the phrase alone fires it.

`home_services`:

```yaml
note_checks:
  - id: pricing_question
    phrases: [pricing, financing, quote, price]
    message: "Prospect asked about price. A person answers this; the AI may not quote."
  - id: system_age_conflict
    phrases: [brand new, installed last year]
    attribute: system_age_years
    flag_when:
      min: 3
    message: "Notes say the system is new, but system_age_years disagrees. Confirm before relying on the score."
```

`system_age_years >= 3` is inside the flag. `1` is outside it.

On load, no approved claim, subject, or CTA may contain a banned phrase. The matcher is the same one the verifier uses, so the word "freedom" does not trip the phrase "free".

Subject templates stay on the M1 allowlist: `{{organization}}` and `{{contact_first_name}}` only. Hook and bridge, in M2, may also use `{{region}}` and `{{sender_name}}`. Those two extra tokens are for AI-written text. They are not added to subject lines.

### phrases.py

One function, `is_banned(text, phrase) -> bool`.

- If the phrase contains anything other than letters and spaces (`$`, `%`, `:`, `-`), match a case-insensitive substring.
- Otherwise match the whole phrase with word boundaries, case-insensitive. "free" does not match "freedom". "limited time" does not match "limited timeline".

`profiles.py` and `verifier.py` both call it. The governance rule covers this file too.

### Exclusions

`apply_exclusions(prospects, pipeline) -> (eligible, excluded)`.

A prospect is excluded when `do_not_contact` equals `do_not_contact_is`, or when `consent_status` is in `consent_status_is`. If both match, the reason is `do_not_contact`. Otherwise the reason is `no_consent`. One reason per person. Input order is kept.

`Excluded` is `prospect_id` plus `reason` (`do_not_contact` or `no_consent`).

Expected from the sample files: b2b excludes only B2B-005 (`do_not_contact`). Home excludes only HOME-005 (`no_consent`).

### Scoring

`score(prospect, profile, pipeline) -> ScoreResult`.

`ScoreResult`: `prospect_id`, `total`, `tier`, `draft_eligible`, `rule_hits`.

`RuleHit`: `field`, `points`, `matched`. Every scoring rule is listed, in profile order. `points` is that rule's weight. `matched` says whether this prospect earned it. `total` is the sum of the weights whose `matched` is true.

Range bounds are inclusive. A missing min means no floor. A missing max means no ceiling. An `in` rule matches the value exactly, case-sensitive.

Field lookup: `last_engaged_days`, `source`, `consent_status`, and `region` come from the prospect. Anything else comes from `attributes`. A missing value does not match.

Tier, from the pipeline file: `hot` when `total >= hot_min` (70), `warm` when `warm_min <= total < hot_min` (40–69), `cold` below `warm_min`. `draft_eligible` is `total >= draft_threshold` (60). A score of 60 would be eligible. These sample rows are not 60.

`qualify(prospects, profile, pipeline) -> (ranked, excluded)` runs exclusions first, scores only the eligible prospects, and sorts by total descending, then `prospect_id` ascending. Excluded prospects have no `ScoreResult`. `score()` itself does not know about exclusions. `qualify` and `verify` are what refuse them.

Hand check, same numbers as the build prompt:

| Id | Total | Tier | Draft | Why |
|---|---|---|---|---|
| B2B-001 | 100 | hot | yes | 30+25+15+20+10 |
| B2B-002 | 75 | hot | yes | misses IT-setup and the 30-day rule |
| B2B-004 | 75 | hot | yes | logistics is outside the industry list |
| B2B-003 | 50 | warm | no | 9 employees, event source |
| B2B-006 | 0 | cold | no | every rule misses |
| B2B-005 | — | — | — | excluded, no score |
| HOME-001 | 100 | hot | yes | 35+15+10+25+15 |
| HOME-004 | 85 | hot | yes | last contact is past 14 days |
| HOME-002 | 75 | hot | yes | condo, young home |
| HOME-006 | 40 | warm | no | referral only |
| HOME-003 | 25 | cold | no | townhome and home age only |
| HOME-005 | — | — | — | excluded, no score |

Ranked b2b: 001, 002, 004, 003, 006. Ranked home: 001, 004, 002, 006, 003. Draft-eligible b2b: {001, 002, 004}. Draft-eligible home: {001, 002, 004}.

Boundary checks call `score` on hand-built prospects and read that rule's `matched` flag. `employee_count` 10 and 200 match the b2b range. 9 and 201 do not. `last_engaged_days` 30 matches the b2b rule. 31 does not.

### Findings

`run_note_checks(prospect, profile) -> list[Finding]`.

`Finding`: `check_id`, `prospect_id`, `message`. One finding per check that fires, in YAML order. Not one per phrase.

Expected:

| Prospect | Findings |
|---|---|
| B2B-001 | pricing_question |
| B2B-004 | headcount_change |
| HOME-002 | pricing_question |
| HOME-004 | pricing_question, system_age_conflict |
| every other sample row | none |

HOME-004 copied with `system_age_years` set to 1 keeps `pricing_question` only. The age flag no longer matches. The word "quote" in the notes still does.

### Schemas the AI fills in M3

All of these use `extra="forbid"`.

- `EvidenceQuote`: `claim_id`, `quote`
- `TailorResult`: `prospect_id`, `claim_ids`, `evidence`
- `DraftEmail`: `prospect_id`, `subject_id`, `claim_ids`, `hook`, `bridge`
- `RenderedEmail`: `subject`, `body`
- `BlockingIssue`: `code`, `field`, `message`
- `VerifyReport`: `passed`, `blocking`, `findings`
- `Funnel`: `sent`, `replied`, `meeting`, `won`, `won_value`, `reply_rate`, `meeting_rate`, `win_rate`, `avg_deal`
- `ScoreResult`, `RuleHit`, `Excluded`, `Finding`, `NoteCheck`, `FlagWhen` live in `schemas.py` as well, next to the M1 models

`passed` is true only when `blocking` is empty. Findings never change `passed`.

### Renderer

`render(draft, prospect, profile) -> RenderedEmail`.

Tokens the filler knows: `contact_first_name` (first word of `contact_name`), `organization` (empty string when the field is null), `region`, `sender_name` (`sender.name`). Unknown `{{tokens}}` are left in place. The verifier is what rejects those. The good fixtures only use known tokens, so the rendered body contains no `{{`.

Subject is the approved subject text, tokens filled. Body, with a blank line between parts:

```
Hi {contact_first_name},

{hook, tokens filled}

{bridge, tokens filled}

- {claim text, one per claim id, in draft order}

{cta}

{sender name}
{sender company}
{postal address}
{opt-out line}
```

An unknown subject id or claim id raises `ValueError`. The renderer does not invent claim text. It does not run the verifier. Footer digits (the street number) are code, and the digit check does not look at them.

For `b2b_001_good`, the subject is `Backups and security for Mesa Ridge Dental`. The body starts with `Hi Dana,` and contains `Mesa Ridge Dental`, both approved claim sentences, the CTA, `Morgan Ellis`, the postal address, and the opt-out line.

### Verifier

`verify(tailor, draft, prospect, profile, pipeline) -> VerifyReport`.

First recompute. Do not trust the caller. Run exclusions on this one prospect. If the reason is set, raise `IneligibleProspect` (a `RuntimeError`). Otherwise `score` it. If `draft_eligible` is false, raise `IneligibleProspect`. The message names the prospect id and the reason (the exclusion code, or the score and the threshold).

B2B-003 raises (score 50, threshold 60). B2B-005 raises (`do_not_contact`).

Then the blocking checks. Text checks read `hook` and `bridge` only, hook first. They do not read the rendered footer, the subject line, or the claim text. Those are code.

| Code | Rule | Message names |
|---|---|---|
| `empty_text` | hook or bridge is blank after stripping | `hook` or `bridge` |
| `unknown_token` | a `{{name}}` whose name is not `contact_first_name`, `organization`, `region`, or `sender_name` | the token, such as `{{price}}` |
| `empty_token` | an allowed token whose value is empty | the token, such as `{{organization}}` |
| `raw_fact` | first name, last name (last word when the name has more than one word), full organization, region, or full email, case-insensitive. Letter-and-space facts use word boundaries. A fact that contains `@` or `.` uses a substring of the whole value | the fact, such as `Mesa Ridge Dental` |
| `digits` | any digit 0–9. A grouped number such as `1,500` is one number | the number, such as `20` or `1,500` |
| `banned_phrase` | the shared matcher | the phrase, such as `% off` or `$` |
| `too_long` | `len(hook.split()) + len(bridge.split()) > max_ai_words`. 90 words passes. 91 fails | the word count |
| `unknown_subject` | `subject_id` is not an approved subject | the id |
| `unknown_claim` | a claim id on the tailor or the draft is not approved | the id, such as `VP-B2B-99` |
| `claim_count` | draft claim count, and tailor claim count, must each be from 1 through `max_claims` | the count |
| `claim_mismatch` | the two `claim_ids` lists differ, order included. A reorder is a mismatch | both lists |
| `missing_evidence` | a draft claim id has no evidence quote | the claim id |
| `evidence_not_in_notes` | after collapsing whitespace and casefolding, the quote is not a substring of the notes, or the quote is shorter than 2 words | the quote |

Each check is its own function. One `BlockingIssue` per miss, not one per code. `field` is `hook`, `bridge`, `subject_id`, `claim_ids`, or `evidence`. The message is an instruction: `Remove the number '20' from bridge; figures are not allowed in AI-written text.` Findings are `run_note_checks` of this prospect, including when the draft fails.

Caught drafts, codes exactly:

- `b2b_001_caught`: `{raw_fact, digits, banned_phrase}`. Hook types the organization. Bridge has `20` and `% off`. Findings still include `pricing_question`.
- `home_002_caught`: `{digits, banned_phrase}`. Bridge has `1,500` and `$`.

The good fixtures pass: `passed` is true and `blocking` is empty. Their findings can still be non-empty. B2B-001 and HOME-002 both asked about price.

Variant tests start from a good fixture and change one thing, so the new code is the only blocking code:

- `{{organization}}` added to the home hook → `{empty_token}`
- `{{price}}` added to the b2b hook → `{unknown_token}`
- both claim lists and the evidence claim id changed to include `VP-B2B-99`, quote left as a real notes quote → `{unknown_claim}`
- both lists set to three approved ids, with a real two-word-or-longer notes quote for the third → `{claim_count}`
- one quote replaced with `purple widgets` → `{evidence_not_in_notes}`
- one quote replaced with the single word `Backups` → `{evidence_not_in_notes}`
- draft claim order swapped, evidence unchanged → `{claim_mismatch}`
- hook replaced with 91 copies of the word `alpha` → `{too_long}`
- the word `freedom` appended to the good hook → still passing, no `banned_phrase`

### Metrics

`funnel(outcomes) -> Funnel`.

- `sent` = every record
- `replied` = replied + meeting + won + lost_after_meeting
- `meeting` = meeting + won + lost_after_meeting
- `won` = won
- `won_value` = sum of won deal values
- rates = that count / `sent`, or 0 when `sent` is 0
- `avg_deal` = `round(won_value / won, 2)`, or 0 when `won` is 0

| | sent | replied | meeting | won | won_value | reply_rate | meeting_rate | win_rate | avg_deal |
|---|---|---|---|---|---|---|---|---|---|
| b2b | 8 | 6 | 4 | 2 | 42000 | 0.75 | 0.5 | 0.25 | 21000.00 |
| home | 8 | 5 | 4 | 3 | 17050 | 0.625 | 0.5 | 0.375 | 5683.33 |

Empty input returns zeros and does not divide by zero. `17050 / 3` rounded to two places is `5683.33`.

### qualify command

`python -m leadgen.qualify --profile <id>`

Calls `assert_not_engaged()` before it loads anything. A kill switch prints the exception message and exits 1. A missing profile exits 1 with one line. Success exits 0.

Plain text. No color. Ranked rows are the eligible prospects only. Findings are printed for every loaded prospect that has one, including someone who was excluded. Funnel reads the profile's outcomes file.

```
profile: b2b_services

Ranked
prospect_id  score  tier  draft
B2B-001      100    hot   yes
B2B-002      75     hot   yes
B2B-004      75     hot   yes
B2B-003      50     warm  no
B2B-006      0      cold  no

Excluded
B2B-005  do_not_contact

Findings
B2B-001  pricing_question  Prospect asked about price. A person answers this; the AI may not quote.
B2B-004  headcount_change  Notes suggest headcount changed. Confirm employee_count before relying on the score.

Funnel
sent 8
replied 6
meeting 4
won 2
won_value 42000
reply_rate 0.75
meeting_rate 0.5
win_rate 0.25
avg_deal 21000.00
```

The source of `qualify.py` takes the profile id from the argument. It does not contain a profile name.

`tests/test_qualify.py` runs the command in-process and checks the b2b ranked line for B2B-001, the exclusion reason, the pricing finding, and `won_value 42000`. With the kill switch on (tmp_path and `chdir`, same isolation as M1), it exits 1.

### Fixture files

Each JSON file has a `tailor` object and a `draft` object. Text is exact.

`b2b_001_good.json` — prospect B2B-001, subject `SUB-B2B-02`, claims `VP-B2B-02` then `VP-B2B-04`.

- evidence `VP-B2B-02`: `Backups 'probably' run`
- evidence `VP-B2B-04`: `Sister practice had a ransomware scare`
- hook: `You mentioned that backups probably run and that a sister practice recently had a ransomware scare.`
- bridge: `If knowing your backups actually work would help, here is what we offer {{organization}}:`

`b2b_001_caught.json` — same tailor and same subject and claim ids.

- hook: `Mesa Ridge Dental deserves better than an IT guy who is family.`
- bridge: `Sign up this month and get 20% off your first three months.`

`home_002_good.json` — prospect HOME-002, subject `SUB-HOME-02`, claims `VP-HOME-01` then `VP-HOME-02`.

- evidence `VP-HOME-01`: `Noisy compressor`
- evidence `VP-HOME-02`: `Asked about financing`
- hook: `You mentioned a noisy compressor and some questions about paying for a new unit.`
- bridge: `Before you decide anything, a quick look can tell you whether a repair is enough:`

`home_002_caught.json` — same tailor and same subject and claim ids. Hook matches the good file.

- bridge: `Like your neighbor, you could get $1,500 off a new unit.`

### Governance

`.cursor/rules/governance.mdc` globs become:

`src/leadgen/verifier.py`, `scoring.py`, `metrics.py`, `exclusions.py`, `findings.py`, `renderer.py`, `phrases.py`

The body stays: "No AI or network imports; pure deterministic Python."

`AGENTS.md` names those same files in the import ban, and adds the M2 smoke command.

## Tests

If a test fails, fix the code, not the test. Sample CSVs are not edited.

- `tests/test_exclusions.py` — b2b excludes exactly B2B-005 (`do_not_contact`). Home excludes exactly HOME-005 (`no_consent`).
- `tests/test_scoring.py` — the totals, tiers, rank order, and draft-eligible sets in the table above. Excluded prospects have no `ScoreResult`. Matched rule weights sum to the total. Boundary prospects for employee count 10, 200, 9, 201 and last-engaged 30 and 31.
- `tests/test_findings.py` — the finding table above, plus HOME-004 at `system_age_years` 1.
- `tests/test_renderer.py` — `b2b_001_good` subject and body contents. No `{{` left in the body.
- `tests/test_verifier.py` — good fixtures pass; caught codes exactly as listed; the nine variants; `IneligibleProspect` for B2B-003 and B2B-005; every blocking message contains its offending text.
- `tests/test_profiles.py` — claims, subjects, and CTAs contain no banned phrase; a note check with `flag_when` and no attribute is rejected; pipeline load asserts `max_ai_words == 90` and `max_claims == 2`; bounds rejection includes 9 words and 0 claims.
- `tests/test_metrics.py` — both funnels and the empty-input zeros.
- `tests/test_qualify.py` — b2b text contains the ranked row, the exclusion, the finding, and the won value; kill switch exits 1.
- `tests/test_domain_agnostic.py` — unchanged, and it still passes.

Smoke test, PowerShell, from the repo root:

```powershell
.\.venv\Scripts\Activate.ps1; pytest -q; python -m leadgen.validate_samples; python -m leadgen.qualify --profile b2b_services; python -m leadgen.qualify --profile home_services
```

Then update `HANDOFF.md` (M2 done, M3 next) and append the new decisions to `DECISIONS.md`. No git commands.

## Out of scope

AI calls, agent prompts, offline replay, the flight recorder, the approval gate, the outbox, the UI, and git commands. Those belong to M3–M5.

Also out of scope, so they are not built beside the real work:

- Scoring a prospect inside `score()` and then hiding the result when they are excluded. `qualify` and `verify` skip them. `score()` stays a pure rule table.
- Running the digit or banned-phrase checks on the rendered footer. The footer is code, and it contains a street number on purpose.
- Editing the M1 prospect or outcome rows.
- A second phrase parser, a plugin registry, or a base class for checks.

## Choices that need a yes

1. **One exclusion reason.** `do_not_contact` wins when both rules match.
2. **`phrases.py`.** One banned-phrase function shared by profile load and the verifier, and named in the governance globs. This is what keeps "freedom" and the claim check on the same rule.
3. **Every rule is listed** on `ScoreResult`. `points` is the weight. `matched` says whether it counted. The total is the sum of the matched weights.
4. **`flag_when` is inclusive.** A note-check attribute must be declared on the profile. `flag_when` requires an `int` attribute. A check with an attribute and no `flag_when` fires on the phrase alone.
5. **Claim ids are compared in order.** Swapping the two claims is `claim_mismatch`.
6. **Findings are printed for every prospect** the file loaded, including an excluded one. The ranked table is eligible prospects only.
7. **`test_qualify.py`** locks the command output and the kill switch. The smoke line still runs both profiles.
