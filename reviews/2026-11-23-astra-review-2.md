# Astra review 2 — 2026-11-23

The trust boundary and category extension work are substantial improvements. Do not close all P0/P1 findings yet: resolution still loses semantics, persistent identity drops a scope component, and acceptance versions have already drifted.

Scope: only the five requested reports, policies.yaml, identity.py, and resolve.py were read. No build, importer, schema, adapter, ledger, published JSON, or original review was inspected; no tests were run. Finding numbers below come from the round-2 report, not an independent reread of the original review. “Reported fixed” means implementation evidence is a report, not verified end to end. Chargers have no category-specific evidence in this reading set.

Citation aliases (paths relative to repository root; line ranges refer to current files):
- **R2** = `team/reports/2026-11-22-a3-impl-r2.md`
- **R3** = `team/reports/2026-11-23-a3-impl-r3.md`
- **SSD** = `team/reports/2026-11-23-a3-impl-ssds.md`
- **REV** = `team/reports/2026-11-23-a3-impl-revisions.md`
- **RTR** = `team/reports/2026-11-23-a12-routers.md`
- **POL** = `data/decisions/policies.yaml`; **ID** = `scripts/identity.py`; **RES** = `scripts/resolve.py`.

## 1. Prior P0/P1 disposition

| Finding | Disposition | Evidence and remaining limit |
|---|---|---|
| P0-1: trusted publication vs candidates | **Reported fixed mechanically; acceptance quality remains open.** | R2:4–12,39,52–53 reports replayable decisions, accepted/approved-only publication, preview separation, and replay tests. POL:1–3 describes the boundary. Broad and mutable policies below can still admit incorrect trusted facts; publisher/decision enforcement was outside scope. |
| P0-2: preserve claim semantics | **Partial; not closed.** | R2:36–38 reports full claim storage. RES:77–107 implements supersession and exact headline-condition grouping; RES:24–74 separates kinds. But equal numeric values collapse distinct qualifiers, conditional rows discard qualifiers, and primary measured claims lose measurement modes (risk 2). |
| P0-3: scoped identity and unsafe merging | **Partial; core primitives fixed.** | ID:22–34 verifies GTIN length/check digit and padding; ID:37–63 provides issuer-aware normalization and level-scoped keys. Quarantine, GTIN lookup exclusion, split veto, and proposal-only suffixes are reported in R2:32–35; 85 actual GTIN conflicts are reported excluded in R3:18. Persistent anchors omit level (ID:66–68); cross-market exact merges also need review (risk 4). |
| P1-4: inheritance | **Reported fixed for ordinary hierarchy; revisions incomplete.** | R2:42–43 reports approved-parent inheritance and ancestor provenance. RES:127–134 blocks family inheritance and package physical/shipping facts; RES:137–151 orders parents and reports cycles. Revision applicability is not explicitly represented in RES:123–134; cycle reporting alone does not establish publisher rejection. See risk 3. |
| P1-5: normalization/units/qualifiers | **Reported fixed at normalization; partial end to end.** | R2:44–45 reports unit conversion, integer checks, ranges, and qualifiers. REV:4–9 supersedes RTR:6–7: custom-unit schema mismatch is fixed and profiles declare units. RES:35–49,92–95 still loses qualifier distinctions downstream. |
| P1-6: regional coverage | **Still partial.** | R2:46,56 preserves observations but defers non-US claims; R3:7 says 6,511 non-US MTMs remain raw-only, and R3:54 still defers the claims store. Observation retention is not queryable non-US claim coverage. |
| P1-7: stable IDs/replay | **Partial; not closed.** | ID:79–90,103–118 reserves issued/tombstoned IDs and reuses anchors. R2:40–41,52–53 reports stable claim IDs and replay. REV:27 records removal/re-minting of 245 uncommitted registry entries; whether any IDs escaped into published artifacts is unverified. ID:66–68 drops level, and version drift weakens historical replay (risks 1,4). |
| P1-8: schema/category extension | **Reported fixed for validation and adding categories; broader closure unverified.** | R2:49–50 reports profile/claim/detail validation; R3:30–38 reports removal of hardcoded categories plus an independent widgets fixture. REV:14–16,24 supersedes RTR:8–9 with revision publication/schema/smoke support. No schemas/tests inspected; scaling work remains deferred (R3:54). |
| P1-9: fetch/cache/304/durable failures | **Open; no closure evidence.** | R2:56–57 explicitly defers it. SSD:11–12 adds a concrete parsed-cache hazard: parser edits require manual cache regeneration and `--reparse` does not rewrite that cache. No later report establishes a fix. |

Other previously deferred items: category registration and revision fixtures now have reported coverage (R3:30–38; REV:23–24). Apple multi-identifier splitting, ASUS adjacency identity, typed CTO constraints, interval facets, and the million-row benchmark have no closure evidence here (R2:58–60; R3:54–55). The v0 payload was trimmed, not removed (R3:42).

## 2. Top five risks, ranked

### 1. P1 — Auto-accept scope and immutable versioning are weaker than advertised

POL:6–21 and 47–62 accept normalized claims without key allowlists; POL:22–37 accepts whole type classes plus free-text exceptions. Type validity does not establish correct subject, option, unit basis, or applicability. The relation rule accepts `adapter:*` and `page-variants:*` for four relationship types without source/version constraints (POL:158–166), even though ASUS adjacency remained deferred (R2:58). Future adapters can inherit approval by method naming alone.

More concretely, POL:1,12 requires new policy IDs for changed acceptance and audited parser versions, yet REV:20,28 reports parser @1 retained and router policy @1 edited in place. SSD:11 also retains parser @1 after semantic fixes, albeit explicitly before initial publication. Identical replay digests across repeated current runs prove determinism, not recovery of earlier semantics. Reports request coordinator confirmation (R2:12; R3:11; SSD:13; RTR:11); this reading set contains no confirmation evidence.

**Action:** use explicit source/extractor/key/relationship allowlists, record audit approval, and enforce immutable policy content per ID. Separate raw snapshot identity from parser version so parser bumps do not orphan fetched evidence. Releases should identify raw inputs, parser/code revision, profile/normalizer versions, policy content, ledger, registry, and output digest.

### 2. P1 — Resolution still turns qualified or differently measured facts into misleading values

RES:35–38 groups primary claims by value alone and retains the first `nx`. Thus exact 100 and “up to 100” become one known value whose qualifier depends on claim order. RES:51–53 omits qualifiers from conflicting alternatives; RES:92–95 omits even a single conditional group's qualifier/display. Primary measured claims are also grouped by value alone; only secondary kinds preserve `mmode` (RES:62–67), so measured-only results lose mode or manufacture conflicts across unlike methods.

This matters now: SSD speeds use a cache headline condition and unresolved per-capacity caveats (SSD:8–9,34; POL:97–99). “Up to” does not by itself prove a specific cache state; that condition needs evidence or explicit derivation. ENERGY STAR power basis and DisplayHDR CTS versions already produce reported conflicts (R3:11,15–17,54). Visible conflicts are preferable to silent selection, but incomparable test bases should be represented as conditions/modes.

**Action:** retain qualifier, mode, and claim provenance in every result branch; define equivalence on semantic assertions rather than numeric value alone. Add order-reversal cases for exact/bounded values, conditional bounds, and measured-only modes; model certification/test basis and capacity caveats explicitly.

### 3. P1 — Revision entities exist, but version applicability remains under-specified

REV:12–21 reports working revision locators, 245 entities, own-spec summaries, and CPU/RAM/flash/default firmware facts moved to the default TP-Link revision. This resolves the earlier missing entity path. It does not prove that remaining model-level Wi-Fi/port/physical facts apply across revisions: the fetched HTML is identical across version URLs (RTR:12), and only selected fields were moved (REV:19).

RES:123 omits `revision` from its level map, while RES:127–134 uses a default model level and has no revision-specific applicability rule. That is a concrete fallback, not proof of an observed wrong published value; importer/publisher were not inspected. Own-only revision summaries avoid one presentation error, but inherited detail values need the same scrutiny. Preview revision discovery and UI are explicitly unfinished (REV:17,29–30).

**Action:** distinguish “all revisions” from “unspecified/default revision”; inherit only facts with established applicability. Test two revisions with contradictory radio/port/CPU facts and an unspecified model fact, asserting both detail and summary behavior. Verify whether re-minted IDs were ever externally visible; if so, preserve redirects/tombstones (REV:27).

### 4. P1 — Stem proposals are safely isolated, but exact matching and durable anchors remain risky

Credit: 106 cross-source stem links remain proposals, none approved, and transmit no claims (R3:12–14; POL:82–83). Keep that boundary; missing Lenovo marketing-name matches (R3:55) are a coverage problem, not grounds for broader automatic merging. A matching stem cannot establish shared revision, regional identity, or certification applicability.

R3:12–13 says exact normalized manufacturer-model matching deliberately ignores market. That requires a brand/category-specific guarantee, not merely equal strings. Separately, ID:58–68 includes level in the matching key but removes it from the persistent anchor; a model and configuration with the same category/scheme/issuer/value/market therefore share an anchor. ID:85–86,112–117 neither checks stored kind nor detects rebinding there. Actual collision incidence is unverified, but the identity primitive loses its own scope guarantee.

**Action:** preserve level in versioned durable anchors, with compatibility migration that retains existing IDs and flags ambiguity. Test same identifier across levels and markets. Keep stem links non-transitive and ledger-reviewed, with explicit evidence for any certification transfer or entity merge; scope exact cross-market merges deliberately.

### 5. P1 — Regenerated JSON in main accumulates history beyond the live payload budget

The current ~100 MB figure is user-supplied, not measured here. R3:40–43 distinguishes 68.1 MB logical payload from 102 MB filesystem allocation and suggests ~80 MB; SSD/routers/revisions subsequently add output. Hash directories address file layout, not total bytes or retained Git history. Removing preview quote/raw text saves bytes but sacrifices evidence and does not remove old blobs.

**Proposed budget:** measure logical uncompressed bytes, file count, compressed transfer size, changed output bytes per release, and packed Git size separately. Warn at 100 MiB live API output; require an explicit budget increase above 150 MiB. Set a 250 MiB packed source-repository warning and a 500 MiB migration trigger; these are project targets, not hosting limits. Track monthly growth: 100 MB of genuinely new blobs per daily release is ~3 GB/month before compression/delta savings, not a prediction that every rebuild costs 100 MB.

**Strategy:** retain source, decisions, identity registry, and small release manifests in main; publish generated JSON to external object storage under immutable release prefixes plus an atomic current pointer. Keep the latest 10 releases or 30 days as an initial retention rule, with intentional long-term releases archived separately. Alternative: publish an orphan, single-snapshot `gh-pages` branch and replace it by force-push on release; ordinary commits or force-pushing a branch that retains parents do not bound history. Keep release provenance outside that disposable branch. Neither approach immediately shrinks existing main history or guarantees immediate host garbage collection; assess a separately coordinated history cleanup only if measured size warrants it.

## 3. Three highest-value next steps

1. **Repair trust/replay governance before expanding policy coverage.** Freeze existing policy meanings, issue new IDs for changed router acceptance, decouple snapshots from parser versions, and constrain broad claim/relation policies. Exit criterion: one pinned release reconstructs the same accepted facts and digest after current parsers/policies advance; audit approvals are explicit.
2. **Close semantic and identity holes with a small adversarial fixture suite.** Cover qualifier/order preservation, measured-only modes, revision applicability, cross-level anchors, cross-market exact IDs, and stem links that must not transmit certification. Exit criterion: no lossy assertion collapse, wrong revision inheritance, or automatic identity/certification transfer in those cases; stable existing public IDs survive migration.
3. **Move generated publication out of main and enforce measured budgets.** First baseline logical payload and packed/history growth, then publish an atomic versioned release with manifest and retention policy. Exit criterion: normal rebuilds add no bulk JSON to main, rollback selects a retained release, and CI reports/fails the agreed budgets. Do not trade away provenance merely to meet the size target.
