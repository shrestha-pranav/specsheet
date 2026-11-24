# A1+A2: USB chargers v1 + title matcher, 2026-11-24

## Decisions / open questions first
- **Coordinator: approve `claim/mfr-chargers-structured@1`** (pending, locked by the import). It covers 11 stores with per-source key allowlists and
  normalised labelled rows only. It does not accept gen.gan, gen.form_factor or gen.product_line (all title-derived), pd.protocols (raw maker tokens),
  id.msrp_us or any status-unknown claim.
- **Result:** chargers = **142 trusted + 45 preview-only = 187 models** from 13 brands: Belkin 42, Anker 28, UGREEN 26, CHOETECH 18, AUKEY 18,
  Satechi 13, HyperJuice 7, Native Union 7, mophie 7, INIU 7, Plugable 6, CUKTECH 4, Nekteck 4. 704 claims accepted. **Short of the 200 target.**
  I did not pad it with Baseus: its stores print only colour SKUs and its specs are images. Apple/Samsung/Google stores are JS-rendered. Lisen and
  ESR use Amazon ASINs as SKUs.
- **v0 gan-chargers is retired** from categories.json. Of its 150 ids:
  50 kept (45 same slug; 5 Anker A/B relabels pre-bound in registry.jsonl, e.g. anker-a2692 = model B2692); 19 redirected via tombstones.jsonl
  (3 split into Belkin channel twins WCH013+BBC013); 81 retired with a reason (Baseus 36, Spigen 9, EcoFlow 7, gone from US stores);
  `category:gan-chargers` -> `chargers` in redirects.json (small app.js hook). Open: 5 kept ids are preview-only (iniu-a21-e1, iniu-i624,
  satechi-st-uc100wsm/-tc100gm/-tc108wm), so their trusted URL 404s until a value is accepted.
- **Semantics to confirm:** `out.max_total_w` = maker-labelled total (best combination); `out.all_ports_w` = all ports at once, only with explicit
  membership (a combination naming every port, or "N Ports in Use" with N = printed port count; A2688: 100 W total, 89 W all ports). A single
  unlabelled wattage (Belkin Wattage, mophie Output) is `out.rated_w`, unresolved when the title prints another (BBC032: title 65W, row 20W).

## Matcher (`scripts/match.py`; CLI `--json`; `match(title, category=None)`)
- Match bases, strongest first: exact model number / identifier, then exact alias (every token of a name or alias), then brand + marketing name
  (every distinctive token). A basis must leave exactly one product; a tie returns nothing, with the reason in `diagnostics`.
- Guards: title brand/category must agree; printed W/TB/mAh/inch/port count must agree; variant tokens (3-digit marketing numbers, II/III,
  Pro/Max/Mini...) must be in the product's own names; a multipack listing never matches a single unit.
- **Tuning set** (tests/fixtures/match_titles.jsonl, 88 titles: chargers 41, power banks 9, SSDs 9, monitors 8, TVs 8, routers 3, 21 negatives):
  **precision 1.000, recall 0.970** (65 TP, 0 FP, 2 FN). The misses: a capacity-only SSD title (see open issues), and the router tie "Archer AX55
  AX3000".
- **Held-out set** (match_titles_heldout.jsonl, 20 titles written before running): first pass **precision 0.875, recall 0.933**; after one general
  fix (multipack guard) **0.933 / 0.933**. Remaining FP: model A2687 printed with "140W" (it is 160W); the identifier wins at confidence 0.82 with a
  `conflict` note, so a >=0.85 threshold drops it. Caveat: I wrote both sets knowing the catalogue; expect lower on a real deal feed (run that next).
- `lookup/aliases.json` = 41.9 KB: 634 phrases that differ from published names, including 19 v0 pilot names such as "511 Charger (Nano 3)".
  build.py regenerates it.

## How robust is charger identity (frank)
- **Strong:** Anker (5-char stem; titles carry 735/737 + Nano II/3), Belkin (WCH/BBC/CCx), AUKEY/CHOETECH (code in maker title), HyperJuice.
- **Weak:** UGREEN item numbers are per colour/edition (Uno 65W 15570 vs 35856 = same hardware, two models); Plugable puts colour in the model
  (PS-30C1B/W); mophie has a part number only; Satechi/Native Union rely on SKU-stem rules I inferred.
- **Not asserted:** Anker A/B relabels (A2735/B2735 "323 Car Charger" stay two) and channel twins (BBC013 vs WCH013). Marketing names collide by
  design (715 and 735 are both "Nano II 65W"), so name-only titles are often unanswerable; the matcher returns nothing rather than guess.

## Sources (honest UA, robots honoured, 1 req/s, no Bright Data)
- New `_charger.py` (imports `_powerbank` unchanged, so power-bank fingerprints did not move), `anker_chargers.py`, `belkin_chargers.py`,
  `shopify_chargers.py` (12 stores). 214 pages, all 200. Blocked: voltme (403), cablematters (robots). SHARGE prints no model. See manufacturers.yaml.

## Verification
- `RELEASE_DRY_RUN=1 scripts/release.sh "chargers v1 + matcher"`: rc=0, budget ok (API 91.7 MiB), releases/20261124T101659Z-d4be7842.json; strict
  parsers, smoke, frontend-smoke, all tests incl. new test_chargers.py (14) + test_match.py (5) pass. Nothing committed/pushed; no stash/checkout/reset.

## Shared-file changes (all minimal, made under /tmp/specsheet-release.lock)
- registry.py +14 SOURCES; policies.yaml +1 pending policy; policy-lock +1; registry.jsonl +5 pre-binds + minted ids; tombstones.jsonl +101.
- build.py: gan-chargers category and models.json dropped, `match.write_aliases` called. app.js: category redirect + retired-record message.
- Untouched: import.py, v1_publish.py, _powerbank.py. New: research/chargers/*, 4 adapters, match.py, 2 tests, 2 fixtures, raw/<14 sources>.

## Open issues
- **SSD bug found by the matcher:** Samsung/WD config names carry the wrong capacity (MZ-V9P2T0B/AM and MZ-V9P4T0B/AM both "990 PRO 1 TB";
  WDS100T4X0E "500GB"); capacity-only titles cannot match until fixed. browser-smoke.mjs still targets `#/category/gan-chargers` (not in release).
  Next T0 source: USB-IF certified list (PD/EPR). AUKEY/Plugable/Nekteck specs need OCR.
