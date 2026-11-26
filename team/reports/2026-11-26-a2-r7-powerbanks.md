# A2-pb r7: power-bank PPS + surge makers (2026-11-26)
**Result:** +12 pd.pps true (11 stated, 1 derived via the SFC 2.0 ruling), 0 other claim changes, 0 HTTP requests (all from stored maker
snapshots). Surge: no new brand published (Belkin is the only one feasible and would lower the gate; see below).
## Presets (docs/api/v1/presets.json, before -> after)
- power-bank-samsung-45w pd.pps: 21/129 = 16.3% -> 32/129 = 24.8% (matches 20 -> 30). EcoFlow joins the covered brands (6 now). Gate still fails (80%).
  Remaining gap: 45 in-scope rows (Belkin 29, mophie 16) print no PPS on any page we may fetch.
- surge-ul1449-2000j: 61.9% -> 61.9% (unchanged, 2 brands).
## Decide / open questions
- **Approve 2 pending policies** (approval fields left empty; both were locked by my import at 08:35Z):
  - `claim/mfr-power-banks-structured@8` supersedes @7 (@7 retired verbatim). Official kind only. WIDENING: pd.pps is added to ecoflow-us-powerbanks.
  - `claim/derive-samsung-sfc2-pps@1`: kind derived, key pd.pps only, extractors anker/iniu/cuktech @6.
- **EcoFlow FAQ:** I accept a FAQ answer on the product's own page only if the page passes the spec-name gate, and a FAQ that names a product line ("RAPID Pro") must match the page title.
  3 of the 4 are an "Output supports ... PPS" clause. 1 (RAPID 25K 100W) is the generic "protocols that support fast charging? .../PD3.0/PPS" list. Drop that branch if it counts as too weak.
- **Belkin surge:** 54 strips are stored (crawlpy-strips@1, preview only, no policy): joules 54, outlets 53, UL 1449 9, bare "Clamping Voltage 330V" 18.
  Publishing them gives 3 brands, but the min fill drops from 62% to about 57%. Choose: a crawlpy-strips@2 policy (bare clamping -> vpr_max, the CyberPower/Tripp Lite precedent) or keep preview.
- **Domains needed (A2-tuv):** www.apc.com / www.se.com (APC; pages are JS-rendered), www.eaton.com (Tripp Lite already covered). None fetched.
- **Skipped:**
  - Samsung: human_only.
  - Baseus: no adapter (specs are images).
  - KUXIU: PPS only in a customer review.
  - Belkin and mophie pages: never print PPS.
  - SHARGE Storm 2 / IceMag 2: no model number (absences).
  - INIU B62: SFC 2.0 only in image alt text.
  - Anker A1657: "Super Fast Charging" without 2.0.
## New values (pd.pps true; no new PPS ranges: prose and derived rules never write one)
- INIU P73-E1, P771, P781, SnapGo 10K 25W, SnapGo P71-E1: from the per-port "Supported Protocol ... Output port: USB-C / USB-C Cable : .../PPS" block, which the old splitter cut at "Input".
- CUKTECH PB100P, PB200U: from a feature bullet ("protocols, including PD, PPS, ...").
- EcoFlow RAPID Pro 20K, Pro 27K, Pro X, RAPID 25K 100W: from the FAQ.
- Anker A1638: derived, basis=derived, from "Only the USB-C port / cable supports ... 45W max for Samsung".
- Check: claim diff of HEAD parsers (git worktree) vs new over all 9 bank sources + ecoflow-us-stations: 1879 -> 1891 groups, exactly 12 new, 0 changed or removed. Stations 0 changes.
## Shared-file changes
- New `crawler/adapters/pb_pps_r7.py`: INIU/CUKTECH subclasses (@6) + `sfc2()`/`add_derived()`.
  shopify_powerbanks.py is untouched (shopify_powerstations imports it, so editing it would move the station pins). UGREEN stays @5.
- `registry.py`: iniu/cuktech module -> pb_pps_r7 (2 lines).
- `anker_powerbanks.py` @6: derived rule over prose + htmlContainer notes.
- `shopify_powerbanks2.py` @6: `ecoflow_faq_pps()`, and `_Shop2.version = VERSION` (it used to inherit 5). sharge/kuxiu/mophie: version bump only.
- `research/power-banks/spec-profile.yaml`: basis enum + `derived`.
- `policies.yaml`: +@8, +sfc2@1, @7 retired. `policy-lock.jsonl`: +2 lines, written by import.
- Tests: new `tests/test_r7_powerbank_pps.py` (10 tests). `tests/test_review3.py`: Policies NEW/OLD -> @8/@7.
- Appended r7 sections to research/power-banks/merchants.md and research/power-strips/merchants.md.
## Build
- `flock ... import.py --strict-parsers` rc 0. `flock ... build.py` rc 0.
- test_r7_powerbank_pps, test_preset_fill_powerbanks and test_review3 pass. Full suite not run. release.sh not run.

## Addendum: coordinator rulings (2026-11-26, 00:58)
- EcoFlow RAPID 25K kept: the product's own FAQ states PPS for that SKU.
- Belkin surge published under pending `claim/mfr-strips-belkin-printed@1`. It accepts printed keys only: type.ul1449_listed (9), surge.joules (54), outlets.count (53) and surge.clamping_v (17: 330V x13, 400V x2, L-N/L-G/N-G split 400/500/500 x2, stored as the highest mode with the literal kept). Never surge.vpr_*: no Belkin page says VPR, so 'Clamping Voltage 330V' is not a VPR. Skipped: '340V(@50A)', '340(@ 100A)', 'UL1449 1.2 KV'.
- New spec key `surge.clamping_v` added to research/power-strips/spec-profile.yaml (important, facet, why/traps).
- Surge preset surge-ul1449-2000j: 61.87% -> 54.21% (gate key surge.vpr_max 232/428; UL 1449 243/428, joules 299/428). Belkin shows as not_covered on VPR (no value), as ruled. Samsung-45W stays 24.81%.
- Code: new `crawler/adapters/crawlpy_strips_belkin.py` (supplement extractor `crawlpy-strips-belkin@1`). crawlpy_strips.py is untouched, because rel/source-stated-hierarchy@10 (approved) pins crawlpy-strips@1 for Belkin page variants. A bump would have demoted that approved policy.
- `registry.py`: belkin `supplement` key, `supplement_parsers()`, and iter_observations dispatch to the supplement.
- `scripts/import.py`: 1 line, `current_fp.update(registry.supplement_parsers())`, so the supplement is drift-checked.
- New test: `tests/test_r7_belkin_clamping.py` (7 tests).
- source-policy 2026-11-25.6 -> 2026-11-26.1 (validate ok):
  - www.se.com and www.apc.com added as maker, crawl agent. Robots has only `*` path disallows. The 2014 terms have no automated-access clause. to_clear flags the "personal, non-commercial" reproduction clause and the no-hyperlink clause for owner review.
  - www.eaton.com added as human_only, evidence blocked (robots.txt 403 Akamai).
  - www.belkin.com categories += power-strips.
- APC adapter not built: SurgeArrest URLs redirect to /us/en/all-products and the US product sitemaps hold no SurgeArrest strips.
- Eaton: no fetch attempted. Tripp Lite is still covered through the existing tripplite source.
- Build:
  - `flock ... import.py --strict-parsers` rc 0. The first try hit drift on another agent's in-flight imgattach@1 change; it passed after they re-pinned.
  - `build.py` rc 0. Belkin clamping_v is in the static JSON.
  - Lock lines written by import.
