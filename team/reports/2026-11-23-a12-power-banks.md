# A1+A2: power banks (category #8), 2026-11-23

## Decisions / open questions first
- **Result:** power-banks = **118 trusted model rows + 124 preview rows**, 5 brands (Anker 22, Belkin 37, INIU 34, UGREEN 23, CUKTECH 8). 807 known
  specs, 13 conflicted. All conflicts are Anker pages where the maker's two tables (variant key_parameter vs the Specifications table) disagree.
  Import accepted 874 claims and left 378 as candidates. 124 ids minted, 0 conflicts. Profile: 39 specs in 7 groups, validates against the schema.
- **Coordinator: approve `claim/mfr-power-banks-structured@2`** (state pending). It has per-source key allowlists, accepts only normalised
  values, and no prose-, title- or price-derived keys.
  **@2, not @1:** after the first import locked @1, I found that the shared PDO parser derived wattage from V x A (19.98 W from 9V2.22A) and
  published it as official. I fixed the parser. Because the fingerprints changed, I issued @2 and moved @1 verbatim to `retired_policies`.
  Neither was ever released.
- **Incident (fixed, tell the robovac agent):** while I was cutting my @1 block, `claim/mfr-robovac-structured@1` was sitting between it and
  `relation_policies:`, so it was carried into `retired_policies` for about 2 minutes. I put it back verbatim in `claim_policies`. Its hash matches
  its lock line (4ec767d1). If they ran an import in that window, their policy did not apply. They should re-run.
- **Incident 2:** my first dry run overlapped the robovac agent's dry-run `release.sh` (both rebuild docs/api). It produced a bad manifest:
  `releases/20261123T133711Z-c527daf5.json`, plus its line in `releases/index.jsonl` (1.3 MiB API, 158 files). I left both in place (append-only
  log). The rerun is good: `releases/20261123T134128Z-c527daf5.json`, 72.6 MiB, 14,418 files, local gh-pages 075274b3. Please drop or ignore the
  bad one. Two agents running `release.sh` at once corrupt each other: serialize it (lock file?).
- **Semantics to confirm:**
  - `out.max_total_w` is the all-ports-at-once total as printed (the INIU P41 total is 15 W, while its single port does 45 W).
  - Belkin's 'Wattage' row (single port or total is not stated) goes to its own key, `out.max_output_w`.
  - Belkin's "10K" is `cap.class_mah`, never `cap.cell_mah`.
  - Wh is never computed from mAh.

## Opaque specs, what the sources really give (accepted model counts)
- cell mAh 69, class mAh 37 (Belkin), **Wh only 13** (UGREEN 'mAh/3.6V/Wh', CUKTECH 'Cell Capacity', Anker FAQ), rated 5 V mAh 5 (CUKTECH),
  port PDO tables 50, total output 37, single-port 44, input 36, weight 50, chemistry 8, PPS 20.
- Traps seen and handled:
  - Anker A1657 prints 'Battery Capacity 5,000mAh, 7.4VDC / 37Wh (Two Cells in Series)' next to 'Total Capacity 10,000mAh'. Any series-pack
    voltage of 5 V or more blocks a cell-mAh claim.
  - UGREEN '20,000mAh/72Wh (14.4V*5000mAh)'.
  - CUKTECH '74Wh/75.5Wh' (the lower value is kept, both stay in the literal).
  - INIU prints every port combination; the `out.simultaneous` literal keeps them all.
- Not on store pages: cell voltage (mostly), chemistry (except CUKTECH/UGREEN/Belkin BoostSolid), airline flag (derived, stays preview).
  Pass-through, display and wireless are prose-derived and stay preview.

## Sources (honest UA, robots honoured, 1 req/s, no Bright Data)
- Adapters built and run (143 pages, all 200):
  - `anker_powerbanks.py`: product sitemap + /collections/power-banks; reads __NEXT_DATA__ variants and the spec tables.
  - `belkin_powerbanks.py`: US variant sitemap, colour SKUs grouped into 37 models; JSON-LD + spec table.
  - `shopify_powerbanks.py`: INIU/CUKTECH/UGREEN products.json + page spec block + /products/<h>.json.
  - Shared parsers live in `_powerbank.py`, reusing the GaN pilot's PDO model.
- Viable, not built: EcoFlow (Wh on all 18 pages), mophie (149 handles), SHARGE, KUXIU (semi-solid), Baseus (specs are images; store SKUs are
  colour SKUs). Details in manufacturers.yaml.
- **Blocked:** ChargerLAB. robots.txt explicitly disallows ClaudeBot/anthropic-ai/Claude-Web (Content-Signal ai-train=no), so I fetched nothing.
  Anker /products.json returns 404 (headless store).
- CPSC recall API works (33 power-bank recalls). Model strings are in free text, so I did not build an adapter; the `safety.recall` key is reserved.
- Identity: the model number is the key and colour SKUs are aliases. A110G (Wukong edition) stays its own model. Belkin BBA0xx and BPB0xx on the
  same slug stay separate models, as stem proposals at most. Pages that print no model number are not minted: INIU 3, CUKTECH 6, UGREEN 2.

## Verification
- `import.py --strict-parsers`: parser drift 0.
- `build.py` passes. smoke passes: 8,216 products, 9 categories. frontend-smoke passes.
- All 5 test files pass (adversarial, identity, new_category, replay, resolve).
- `RELEASE_DRY_RUN=1 scripts/release.sh "power banks"` rc=0, budget ok. Nothing committed or pushed.
- No git stash, checkout, reset or restore was used.

## Shared-file changes
- `crawler/adapters/registry.py`: +5 SOURCES lines (anker/belkin/iniu/cuktech/ugreen-us-powerbanks, importer `model`).
- `data/decisions/policies.yaml`: +`claim/mfr-power-banks-structured@2` (active); @1 retired verbatim; robovac @1 restored, as described above.
- `data/decisions/policy-lock.jsonl`: the import appended @1 and @2. `data/_ids/registry.jsonl`: +124 ids.
- `releases/`: 2 dry-run manifests plus index lines (see incident 2). `docs/api` was rebuilt by the release; docs/app.js and styles.css untouched.
- New files: `research/power-banks/{spec-profile.yaml, category.yaml, identity.md, notes.md, manufacturers.yaml, merchants.md}`.
  `crawler/adapters/{_powerbank, anker_powerbanks, belkin_powerbanks, shopify_powerbanks}.py`. Raw data in `raw/<5 sources>/`.

## Open issues
- Anker pages with no spec table: A110R, A1383, A1681, A1685, A1688. Their figures are only in images, so an OCR path is needed.
- Wh coverage is low (13/118). Label photos and manuals are the source.
- INIU's per-port lists rarely carry PPS ranges, even when 'PPS' appears in the protocol list (that alone does give pd.pps).
- UGREEN's Amazon-attribute template pages give only the item number and capacity.
- A4: `out.ports` is a list of objects (name/type/direction/max_w/fixed_pdos/pps); render it as an object_table.
