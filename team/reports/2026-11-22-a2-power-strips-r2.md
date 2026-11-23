# A2 round 2: power strips adapters + crawls - 2026-11-22

## Decisions / results (counts first)
- **Contract**: `crawler/adapters/_contract.py` implements ARCHITECTURE 15.5 (Ref/Discovery/Snapshot/ParseResult, append-only
  `raw/<src>/snapshots.jsonl` + content-addressed `blobs/`, network only via the shared `crawl.Net`). Both adapters expose discover/fetch/parse;
  `parse` is pure over blobs (Tripp Lite shells out to pdftotext on the blob; `--reparse` runs with zero network). One extension:
  `ParseResult.sources[]` (record-level source entries the claims' `source: s1` point to). Derived `raw/<src>/parsed/<key>.json` = rebuildable.
- **Tripp Lite (v2)**: full strip/surge set = **249 datasheet PDFs, 0 missing, 3882 claims** keyed to spec-profile.yaml (surge.joules, vpr_max, cord.*, outlets.*,
  load.*, UL listing, gtin identifier, absences). Eaton address-footer rows fixed (0 of 249 contain them; table parse also repairs wrapped labels such as
  "Outlets Measurement (Center to Center)"). 159/249 state joules; 1 req/s on assets.tripplite.com, sitemap once at crawl-delay 15.
- **CyberPower (v1)** on WP REST: 13 consumer categories (surge 6, general-power 6, rackbar) -> **293 products, 2546 claims**; 640 linked resources resolved
  (638 with a PDF URL); **232 datasheets (-DS) downloaded**, manuals/web sheets recorded as documents only. 166/293 are in the Discontinued category.
  Excluded: metered/monitored PDUs (154), portable power stations, inverters, UPS. 235/293 state joules.
- **crawl.py** for byjasco/furman/austere: **byjasco 1419 products / pages done 1419 (392 strip/surge-ish by title; the rest GE lighting/other)**,
  **furman 65/65 (45 strip/conditioner)**, **austere 18/18 (5 strips)**. byjasco asset stage (images/docs, ~164 MB so far) may still be running in background.
  Fixed crawl.py bug: `body_html=None` crashed `extract()` (byjasco failed first run); now `(feed or {}).get("body_html") or ""`.

## Findings that change the plan
- Model-number patterns are *not* spec predictors: TLP1008TEL 2395 J vs TLP1208TEL 2160 J (more outlets, fewer joules). One record per model number.
- Color pages of the same CyberPower model can disagree on UL listing text (B602RC1 vs B602RC1BK vs GY): per-configuration claims + `conflicted` resolution.
- CyberPower REST has no UPC; `Amperage` row contains data errors ("125 A") so load.max_amps maps from "Maximum Input Current". UL1449 "Clamping Voltage"
  rows ("800V (H-N)", "500V (H-G, N-G)") are mapped to surge.vpr_max as the max listed; the raw string is kept - A1/A3 should add per-mode VPR if they want L-N/L-G/N-G.
- Tripp Lite "UL1449 Let Through Rating" gives bare lists ("500, 400, 500"; mode order unstated), mapped to max, raw kept.

## Files
adapters: crawler/adapters/{_contract,tripplite,cyberpower}.py; raw: raw/{tripplite,cyberpower}/{snapshots.jsonl,blobs,parsed,discovery.json}.
Docs: research/power-strips/identity.md (round-2 section: cord, color, pack, hyphen, HG/RA/OEM rules), manufacturers.yaml (status + counts).

## Open questions
- Validated: all 6428 emitted claims and identifiers pass record.schema.json (claim + identifier $defs); promote.py still to build.
- Which of byjasco's 392 title-matched items are real strips vs extension cords needs the A1 profile `type.kind`; Shopify body_html has no structured specs.
- APC still blocked; Best Buy API key and Amazon alias route still pending coordinator.
