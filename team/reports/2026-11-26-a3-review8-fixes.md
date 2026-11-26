# A3-fix: Codex review-8 fixes (2026-11-26)
Decisions / for the coordinator first:
- 3 new policies, **approval pending**, locked by the bare build (policy-lock.jsonl lines 135-137): `claim/spec-image-power-pdo@2`,
  `claim/mfr-power-stations-structured@8`, `rel/bundle-contents@8`. Their @1/@7/@7 were moved to retired_policies verbatim with a `retired:` line.
  Until you approve them, station claims and spec-image claims are not auto-accepted (power-stations still has 75 trusted rows from other policies).
- `test_adversarial` "every policy is locked" now passes, because the build locked them.
- Naming: 89 SSD configuration names changed (list below). This is deliberately capacity-neutral, so equal-capacity siblings now share a name
  without a capacity. Remaining problem: the parent/page-title fallback can still carry another variant's descriptor (WD My Passport "Gold",
  SN850X "without Heatsink" on the XHE SKU, SN7100S "M.2 2280" on the 2230 SKU). That is not a capacity bug; it needs a per-adapter variant label (A2-st).

Fixes (each with exit-criteria fixtures):
1. P1 alternatives: `build_r2.py gated_alts()` builds pack `a` only from the policy-gated record (`gate()` drops alternatives from disallowed
   sources) and never reads docs `x[*].alt`. Static docs path checked: v1_publish `row_of` already runs on the `gate_view`-gated view, and
   build.py has no alt path. No leak, no change. Fixture `tests/test_build_r2.py::test_alternatives_only_from_gated_records`: a restricted-only
   alt (even if the ungated index carries it) gives a byte-identical index; the authorized alt still gives `disagree`. Live data: 0 alternatives today, so the pack does not change.
2. P1 imgattach: variant/region/shared vetoes (and file-name tokens) now run before both binding branches. Fixtures `tests/test_imgattach.py`
   (OCR variant A2667113 on an A2667111 page with empty file_models, the same without a model mention, UK region, shared SKU): no exact claim.
3. P1 UPS (`_powerstation.ms_figure`, the one reader for rows and prose): "up to / <= / max. / no more than / at most N" -> `up to N`.
   A range ("10-20", "10–20", "10 ~ 20", "10 to 20 ms") becomes an unresolved row claim and writes nothing from prose, so it never becomes an endpoint.
   Prose model tokens keep their suffixes (Plus/Pro/Max/Ultra/Mini/Air/Lite/SE/vN/Gen N), and identity is now exact token equality, not substring.
   Stations @6 -> @7. Claim diff @6 vs @7 over every stored station snapshot: 1665 groups, **0 changed**. Fixtures `tests/test_review8.py`.
4. verdict.ts: a null, absent or blank range endpoint is "no", matching Python `float()` (`pyFloat`). `same()` now uses canonical sorted-key JSON.
   Four parity rows were added to `api-worker/test/fixtures/verdict-rows.json` (null min, null max, alt with reordered keys, alt with a null endpoint).
5. import.py naming: `own_alias` binds an alias that names this SKU (or carries its sku) first. An alias naming another SKU never binds.
   Binding by capacity happens only when no sibling on the page has an equal capacity (±3%). The fallback `neutral_name()` removes GB/TB figures that differ from the config's own capacity.
   Changed names (base import vs new, 13557 entities): Kingston NV3 x6, Samsung 990 x1, TeamGroup G70 PRO / GE PRO / H514 / A440 x24, WD/SanDisk x58
   (SA510, SN810, SN8000S, SN7100S, GX PRO 850X/8100, Extreme Portable V3, My Passport, SN8100, SN850X). Each one dropped a capacity
   that was either another configuration's or not identity-bound.

Checks: bare `import.py --strict-parsers` rc 0 (parser_drift 0), `build.py` rc 0 (both under flock). `npm run pack` was rebuilt locally
(no deploy). `npm test` 26/26, tsc clean. Every test module passes on its own. A full `unittest discover` shows 6 failures
(test_corrections x4, test_replay x2) that pass in isolation and fail the same way without my tests: test-ordering interference, already present.
Shared-file changes: scripts/build_r2.py, scripts/imgattach.py, scripts/import.py (naming functions only), crawler/adapters/_powerstation.py,
shopify_powerstations.py + ankersolix_stations.py (VERSION 7), api-worker/src/verdict.ts + test fixture, data/decisions/policies.yaml (3 blocks + 3 retired),
policy-lock.jsonl (build-written). Tests: test_build_r2, test_imgattach, test_review8 (new), test_a2_r6_dell / test_r6 / test_r7 (policy id pins).
Not touched: A2-pb / A2-st files, source-policy.yaml, registry.py.
