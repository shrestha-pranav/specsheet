# specsheet — structured, cross-brand spec sheets (PROJECT IDEA, pilot in progress)

**Status:** idea + pilot. Started 2026-11-22. Log: `~/code/claude/logs/specsheet/STATUS.md`.

## Why

Reputable brands (Anker, UGREEN, Baseus, ...) do publish specs, but:

- Specs are scattered across product pages, Amazon listings, manuals and *images*
  (per-port PDO tables are often only in a JPG on the listing).
- Every brand uses its own marketing names ("Super Charge", "PowerIQ 4.0", "AVS"), which hide
  the facts that matter, e.g. whether a charger supports **USB-PD PPS** and at what voltage/current.
- No site lets you filter *across brands* by facts like "65 W single-port, PPS ≥ 3 A up to 11 V,
  3 ports, ≤ $25". Closest existing thing: ChargerLAB teardowns/tests (great depth, not a
  structured, filterable catalogue).
- The same model is sold under several SKUs/regional codes, and old SKUs keep selling.

## Idea

A website with one structured record per SKU, per product category:

- **Agent-collected first**: a cheap agent sweeps official brand pages (primary), then retailer
  listings / manuals / FCC filings for gaps, and stores every field **with a source URL**.
- **Crowd-sourced corrections**: users can confirm or dispute a field (e.g. "PPS measured
  3.3-11 V 5 A on a PowerZ meter") with evidence; disputes go to a review queue.
- **Cheap**: plain HTTP fetches and standard web search; no paid scraping browser. Re-crawl
  only changed pages.
- Field-level provenance + confidence (`official`, `retailer`, `third-party test`, `user`,
  `inferred`) so "unknown" is never silently shown as "no".

## Pilot: GaN USB-C wall chargers

Schema: `schema.json`. Data: `data/gan-chargers/<brand>.json` (one file per brand, array of
SKU records). Merge + checks: `scripts/merge.py` → `data/gan-chargers/all.json`.
Brands in the first sweep: Anker, UGREEN, Baseus, CUKTECH, EcoFlow, Belkin, Satechi, Spigen, INIU.

Not self-hosted (no ports, no Caddy route); public prototype on GitHub Pages, see below.

## Prototype site (v0)

- Static site + static JSON dataset, built by `python3 -I scripts/build.py` into `docs/`, served by
  GitHub Pages from `main:/docs`. Rebuild + commit after data changes.
- Merge/quality report: `python3 -I scripts/merge.py --find`.
- Design: `ARCHITECTURE.md` (v0.2; section 0 = accepted review changes). Review: `reviews/2026-11-22-astra.md`.
- Corrections: GitHub issues.

## Consumers

- **bf-deals** (`~/projects/bf-deals/specs.py`, morning deal digest): imports `match()` from `scripts/match.py` over
  the local `docs/api/v1` (never the live site), uses matches at confidence >= 0.9, filters deals by a watch's
  `specs:` block and links `#/product/<cat>/<id>`. A known value that fails excludes; unknown or unmatched is "specs
  unverified", never excluded. Changing `match()` output keys or the product-record `specs` shape breaks it;
  `python3 ~/projects/bf-deals/test_specs.py` checks.

## License

- Code: Apache-2.0 (`LICENSE`).
- Dataset: ODbL 1.0 for the compilation and for values from sources with recorded permission evidence
  (`data/source-policy.yaml`, `licence_grant: true`). Other values are shown as facts with a source link and are
  not licensed by us. Attribution line: "Data: specsheet (ODbL), sources linked per value".
- Documentation prose: CC BY 4.0.

Details in `DATA-LICENSE.md`. Brand, domain and contact placeholders live in one file, `docs/site.json`.
