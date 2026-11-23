# A1+A2: robot vacuums (category #1 of the survey), 2026-11-23

## Decisions / open questions first
- **Result**: 84 models (Dreame 41, Roborock 35, Narwal 8). Published: **60 trusted rows** (Dreame 28, Roborock 31, Narwal 1) + 54 preview rows. Claims:
  683 accepted, 89 candidates. 20 models are identity-only, because their pages have no spec block, so they are not published (GoVac 300-600, C30 Plus,
  D20 Ultra, older L10s, X30 Ultra, X40 Master, 7 Narwal). **The 100+ target was missed (84).** Every other reachable maker either has no spec table
  in its server HTML or is blocked (see below).
- **Identity**: none of the three US stores prints a regulatory model code. mfr_model = the maker's model name (L40s Ultra, Qrevo Edge S5A). The
  maker's material-code SKUs per colour or pack are configuration aliases (010204AA000742, RR-QrevoEdgeS5A5-M2, CP-ZD-A00331-00-00). Grouping
  is by shared SKU, so App Only / Live Only / Membership / Complete / colour pages fold into one model. '+' is canonicalised to 'Plus' (value_raw
  keeps the '+'), so Q7 Max and Q7 Max+ stay distinct. The Roborock "with Refill & Drainage System" variant is its own model `<name> RDS`. FCC ID and
  the label model code are alias_only.
- **Opaque specs are modelled as basis conditions**: `claim_basis` (mfr_in_house_lab | mfr_unstated | third_party_certified | independent_measured) on
  suction, runtime and noise, and `power_mode` on runtime and noise. Claim origin uses existing fields: manufacturer = official + tier manufacturer;
  certification = third_party_certified or a certifier tier; measured = claim kind measured. Of the 29 accepted suction claims, 11 Dreame ones are
  "in-house lab data". No figure is third-party certified (TÜV appears only on tangle claims). Battery is mAh only: Wh is never derived.
- **Coordinator: confirm the new policy** `claim/mfr-robovac-structured@1` (`approval: pending`). It covers labelled spec rows only, with a per-source
  key allowlist. Left as preview: Roborock suction, hot-water and dock flags (Key-Features bullets and title), free text (brush type, voice
  control), object-type counts, and single-instance runtime and noise.
- **Open**: nav.type, nav.obstacle_sensors and mop.type are keyword classes of a labelled cell; trademarks such as "Pathfinder" stay unknown. Is that
  strict enough to be trusted? Plausibility bounds drop Roborock cells that mix robot and dock (S8 MaxV Ultra "Robot Weight 32.19 lbs", Q8 Max+
  "Robot&Dock Size", Q7 M5+ typo). Is dropping them better than storing them as preview?

## Sources (shared crawler UA, robots honoured, <=1 req/s, no Bright Data)
- Adapters: Dreame, Roborock and Narwal US stores (Shopify products.json for discovery, plus a bundle per model = product page + every member's
  /products/<handle>.json, so the parse does not depend on discovery.json). 209 requests in total, all 200.
- Dreame has 4 spec templates plus a 2-model comparison table. The table is read only when its column header names this model (L10s Pro Ultra's
  page is headed "L10s Pro Ultra Heat" and is skipped). Roborock's US store prints only dimensions, weight and battery as a table.
- **Blocked**: Shark (sharkclean.com robots.txt returns 403 WAF).
- **Unstructured** (no spec table in server HTML): Ecovacs (sitemap 404, product list JS-rendered), MOVA (client-rendered compare table, ~18 models),
  eufy (5 robots with T-code SKUs), SwitchBot (6), Lefant (9), Yeedi.
- **Viable_unverified**: iRobot. Its URLs carry real model codes (C975020) and pages have a thin spec list, but the product list is client-side.
- **Not applicable / not probed**: ENERGY STAR (no vacuum category, analyst judgment). FCC (same 403/Cloudflare blocks as the routers round). CSA Matter
  DCL and RTINGS / Vacuum Wars (the certification and measured bases): deferred.

## Shared-file changes
- `crawler/adapters/registry.py`: +3 SOURCES lines (dreame-us-robovac, roborock-us-robovac, narwal-us-robovac). No logic change.
- `data/decisions/policies.yaml`: +1 claim policy, inserted before relation_policies. `policy-lock.jsonl`: its lock line was appended by import.
- `data/_ids/registry.jsonl`: 84 model ids minted. `docs/api/**` was rebuilt by build/release. `releases/<id>.json` dry-run manifests were written.
- No edits to scripts/*.py, schemas/, docs/app.js, or tests.
- New files: crawler/adapters/{_robovac,dreame_robovac,roborock_robovac,narwal_robovac}.py; research/robot-vacuums/{spec-profile.yaml (43 specs,
  validates), category.yaml, identity.md, notes.md, manufacturers.yaml, merchants.md}. raw/{dreame,roborock,narwal}-us-robovac/ (gitignored).
- Coordination incidents:
  - My first plain import.py run overlapped the power-bank agent's build/tests.
  - Two of my dry runs collided with their release.sh: one frontend-smoke 404, and one sqlite "disk I/O error" in import.
  - Both collisions were resolved by waiting for their run to finish.
  - The final dry run ran after the 13:37 policy incident, alone and under the new release lock.
- 7 orphan Roborock snapshots remain in the append-only log under the old ref keys (from before the 'Plus' key fix). Registry skips them.

## Verification
- `import.py --strict-parsers`: 84 robot-vacuum models, 683 accepted claims, 0 invalid claims, no parser drift.
- `build.py`: OK. smoke.mjs: 8,216 products across 9 categories. frontend-smoke: OK.
- Tests: adversarial 24, identity, new_category, replay and resolve all OK. adversarial failed once on power-banks@2 not yet being locked (their change);
  it passed on rerun.
- Final `RELEASE_DRY_RUN=1 scripts/release.sh "robot vacuums"`: rc=0, budget ok, local orphan gh-pages 4614d9d7. Nothing pushed or committed.

## Next (cheapest first)
1. CSA DCL ledger for certified Matter support.
2. Probe the iRobot SFCC product-list XHR (real model codes).
3. Probe the Ecovacs and MOVA spec XHRs (would add ~40 models).
4. Roborock global spec pages or manuals (nav, mop and tank specs).
5. A measured-basis source, pending a licence decision.
