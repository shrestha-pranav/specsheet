# Brief: evidence-backed corrections (PM round 5, D9.2 + D10). Owners: A3 (pipeline, schema, gate), A4 (form, UI). Read common.md, D1, D7, D9, D10.
Goal: a person (or an agent) can fill or dispute one value, with evidence, and an accepted correction becomes an ordinary
reviewed claim. It is reproducible from git, labelled by kind, and removable by a later ledger line. We run no accounts and
keep no personal data.

## 1. Intake (A4)
- Extend `.github/ISSUE_TEMPLATE/field-correction.yml` (keep the payload prefill from `docs/app.js`). Fields:
  `payload` (entity id, key, shown value, release; prefilled) · `claimed_value` · `evidence_type` dropdown:
  **E1** photo of the product's own label/box/manual page (model number and fact in one frame) · **E2** maker page or document URL ·
  **E3** independent measurement URL (a D9 `measurement` source) · **E4** my own measurement (meter/analyser photo + method) ·
  `evidence_url` (required for E2/E3) · `attachments` (GitHub upload, required for E1/E4) · `conditions` (port, brightness, capacity, revision; optional) ·
  checkboxes: **contributor terms** (required; wording in D9.2) · **conflict of interest** ("I work for or am paid by the maker"; optional; such
  a claim is accepted only as E2).
- The form states: "Text alone is not evidence. Photos stay on GitHub; we publish the value and a link to this issue."
- Request links stay as they are ("help us fill this" on failing presets now prefill `evidence_type` and the key).
- `corrections@` mail: a maintainer opens the issue on the sender's behalf (no sender address in the issue, evidence attached by the maintainer).

## 2. Claim files (A3)
- `scripts/corrections.py sync` (read-only `gh api`, labelled `field-correction`, open and closed) writes `data/corrections/<issue>.yaml`:
  `{issue: N, url, entity, key, value, conditions, evidence: {type: E1..E4, url?, images: [{sha256, transcription ≤125 chars}]},
  kind, source: {url, tier}, terms_ack: true, coi: bool, submitted_by: crowd|agent:<role>, synced_at}`. **No handle, no name, no email.**
  The issue URL is the pointer. Images are hashed, never copied.
- Claim kind follows the evidence (D9.2): E1/E2 → `official`; E3/E4 → `measured` (`measurement.mode` from the evidence, e.g. `inspection`,
  `optical`, `advertised_by_device`). Source tier: E1/E4 → `crowd` (url = issue); E2 → `manufacturer` (url = maker page, `via` the issue);
  E3 → `measurement` (url = cited page, `via` the issue). The E2/E3 URL's domain must have a D9 disposition with `free: true`. Unlisted or
  `free: false` domains (RTINGS, TPU `/ssd-specs/`, ssdwiki …) are rejected by `corrections.py check`.
- Extractor `correction@1`; claim id `c_corr_<issue>_<n>` (deterministic). import.py loads `data/corrections/` as a claim source. No
  auto-accept policy may name `correction@1`: **every correction needs a human ledger line.**
- Family scope (SSD): `entity` may be a family id with `applies_to: [config ids]` listed explicitly (A2's seed list). A config is never
  implied. D10 revision guard: `check` rejects a family-scoped `measured` claim with fewer than two evidence samples unless an E2 single-design
  statement is attached.
- Agent proposals: the same file, `submitted_by: agent:<role>`, evidence only from `crawl: agent` domains. An agent never writes the ledger line.

## 3. Review queue and decision (A3, then the reviewer)
- `scripts/corrections.py queue` → `team/queue/corrections.md` (id, entity, key, current value/status, proposed value, evidence type, check
  result, age). There is no LLM decision. An LLM may draft the transcription and flag mismatches.
- The reviewer (a human handle: owner or a named maintainer) checks identity (the model number is visible and matches the entity), that the fact
  is visible, conditions, and the domain disposition. Then append to `data/decisions/ledger.jsonl`:
  `{"id":"d_corr_<issue>_<n>","at":ISO,"by":"<handle>","action":"accept_claim","claim":"c_corr_<issue>_<n>","reason":"E1 label photo, model visible","evidence":"<issue url>"}`
  or `reject_claim` with a reason. decisions.py: allow the optional `evidence` field; nothing else changes. A later line wins, so a revert is one line.
- Close the issue with a link to the release that publishes it (the existing request-loop script).
- Conflicts: a correction that disagrees with a maker value is accepted as a claim. resolve.py then publishes `conflicted`/alternatives as usual.
  It never deletes the maker value. Report the conflict to the maker page owner only through D7 if the maker asks.

## 4. Display (A4, D10)
- Badges: *Maker* · *Maker label (contributor photo)* · *Certified: <body>* · *Derived from <cert>* · *Measured by <source>, <date>* · *Reported by <source>* ·
  *Contributor measurement*. The tooltip gives method, sample, conditions and links (issue + cited page).
- An open, unreviewed correction shows no value: only "A correction is under review (#N)" on the field. Trusted files never carry it; preview may.
- Preset cards: per-kind fill breakdown and "brands covered only by non-maker values". A row with a disagreeing alternative of another kind on a
  filtered key is *might match* ("sources disagree"). `scripts/presets.py` computes both; the UI renders them.
- `/v1/changes` and the release diff mark crowd-sourced changes (`kind`, `tier: crowd`).

## 5. Abuse handling
- ≤10 open corrections per GitHub account (the sync counts from the API and does not store the handle). The rest get `needs-triage-later`.
- Fast reject reasons (templated): no evidence, identity not visible, fact not visible, domain not allowed, duplicate.
- Repeat bad-faith submitters: GitHub block plus label. Nothing about them is stored in the repo.
- A burst (more than 20 corrections per day across all accounts) pauses sync until a human looks.
- Maker self-corrections: welcome as E2 (a maker URL). An E1 photo from a COI-ticked submitter is not enough on its own.

## 6. Licence and policy (A3)
- source-policy: add `github.com/<repo>/issues` as kind `crowd` (`match: path_prefix`; A3 adds that match mode): `free: true, paid: false,
  licence_grant: true` **only for E1/E4 claims with terms_ack**. Evidence for the grant = the form's checkbox text, versioned in the template.
  E2/E3 claims take their cited domain's disposition.
- The relicensing clause for a future alternative licence is held for counsel (Q1). Until then, crowd values are tagged `relicense: false`.
- Takedown (D7) applies to corrections too: `withhold` by claim id.

## Acceptance (fixtures in tests/test_corrections.py)
E1 accepted → official/crowd value fills an unknown; E3 from ChargerLAB → measured value with ChargerLAB credit, no grant; E3 from RTINGS → rejected
by check; family claim with one sample → rejected; reject_claim after accept → value gone next build; correction vs maker value → conflicted with
both shown; trusted index never shows a pending correction; no handle/email anywhere under data/ or team/.
Report: `team/reports/<date>-a3-corrections.md` and `-a4-corrections.md`, ≤40 lines each, shared-file changes listed.
