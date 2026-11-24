# A3: per-source licensing gate (brief pm-2026-11-24-licensing-gate.md), 2026-11-24
`scripts/source_policy.py` is the only reader of `data/source-policy.yaml`. It validates the policy, matches hosts, provides disposition(url), gate(record, tier) and gate_spec, and builds the manifest block and sources.json.
The free tier is gated in v1_publish right after resolution, before rows, facets, lookup, certonly, products.json, counts and preview are derived. build_r2 `--tier free|paid` gates again from the free output. No dispositions were changed.

## Coverage (docs/api/v1/coverage.json = paid manifest block). Records / known values
| category | free | granted | paid |
|---|---|---|---|
| air-purifiers | 1142 / 8016 | 199 / 3260 | 199 / 3260 |
| monitors | 4133 / 38542 | 1465 / 11582 | 1465 / 11582 |
| tvs | 1371 / 31968 | 184 / 1100 | 184 / 1100 |
| laptops | 3001 / 100711 | 0 | 0 |
| ssds, routers, power-strips, chargers, power-banks, power-stations, robot-vacuums | 888/6144, 492/6226, 538/9827, 142/702, 168/1100, 246/1177, 145/1676 | 0 | 0 |
| **total** | **12266 / 206089** | **1848 / 15942** | **1848 / 15942** |
- Granted and paid match the reference exactly (15,942 = 3,260 + 11,582 + 1,100, ENERGY STAR only). No record was omitted by the policy.
- Only laptops drops: 2,002 `port.docking` values are withheld by the F15 expression guard. They are PSREF prose with an `<a href=…psref…>` link. A2 could normalise that text into a fact.
- Free went up in ssds/chargers/monitors because of A2's parallel import (+41 records), not because of the gate.

## Fixtures: tests/test_source_policy.py, 17/17 pass (also with RELEASE=1 in env). Fixture policies in tests/fixtures/source-policy/
- The end-to-end fixture runs the real import.py → v1_publish → build.policy_outputs → build_r2 free and paid, plus a second release on policy v2.
- F1–F16 all pass.
- F1 and F8 grep the whole output tree.
- F3 runs both through gate(support=) and through v1_publish.gate_view.
- F10 checks the diff entry `{key, change: "withdrawn"}` with no previous value.
- F12: build_r2 also refuses a docs tree built with another policy sha.
- tests/test_build_r2.py was ported from `--exclusions` to `--policy`.

## Release dry run: FAILS, by design, at build.py
`RELEASE=1` (now exported by release.sh) stops the build because A2's new adapters cite 11 domains with no disposition (A5 must add them).
Counts are values cited:
- www.dell.com 1975, byjasco.com 1223, www.microsoft.com 532, www.razer.com 453, support.apple.com 231
- learn.microsoft.com 148, www.baseus.com 76, furmanpower.com 52, austere.com 39, plugable.com 14, www.nekteck.com 10
- images.salsify.com is cited by 638 documents only. That is a warning, not blocking: the policy wording is "published value cites". It still needs a disposition.

I ran the remaining release steps by hand on that build:
- smoke.mjs, frontend-smoke.mjs and the size budget (ok) pass.
- Tests pass except two that are A2's in-flight policy work, not this change: test_adversarial (A2's new policy ids are not in policy-lock.jsonl) and test_replay (`rel/source-stated-hierarchy` @2 vs @3).

## Shared-file edits (import.py untouched)
- new: scripts/source_policy.py, tests/test_source_policy.py, tests/fixtures/source-policy/{policy,policy-v2}.yaml
- scripts/v1_publish.py: gate_view() after view() for trusted and preview; records with no allowed own source are dropped from rows, ancestors, bundles and lookup; source tables and documents filtered with licence_grant; markup stripped from names; coverage; new `gate_out` arg.
- scripts/build.py: policy_outputs() writes coverage.json; the manifest is stamped with policy_version/sha, licence fields and attribution; unlisted check.
- scripts/build_r2.py: `--tier`/`--policy`. Removed `--exclusions`/clean_record. Certonly rows are now included. Withdrawn diffs. Snapshots in state/r2-snapshots/<tier>/ (format 2, the first run per tier is a baseline). Manifest has policy, coverage and sha256.
- scripts/site_meta.py: sources.json comes from the policy (granted / facts_only). CREDITS/public_domain removed.
- Other edits: scripts/release.sh (`export RELEASE=1`), schemas/public-detail.schema.json (`sources[].licence_grant`), api-worker/README.md (2 lines).
- api-worker/licensing-exclusions.json deleted; .gitignore adds api-worker/pack/.

## Notes for others
- A4: pages.js still reads `sources[]`/`public_domain`, so the Sources page shows "None listed" until §6 lands. The new shape is `granted[]`/`facts_only[]`.
- The hidden power-strips-demo stays on the static site. The gate drops it from the pack and paid outputs.
- A conflicted value whose disagreement disappears once dropped sources are removed becomes not_published, so the output never hints at a hidden source.
- build_r2 was run into /tmp only. Writing api-worker/pack and r2-data is left to the api agent or coordinator.
