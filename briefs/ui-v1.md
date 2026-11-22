# Brief: specsheet UI v1 (product-agnostic)

You (GPT-6-Astra) are the **coordinator and designer**. Delegate implementation to the
`sol_implementer` agent (GPT-6-Sol), and use `astra_reviewer` for an independent critique.
Use the **impeccable** skill (installed at `.agents/skills/impeccable`) throughout.

## The product
specsheet: a cross-brand catalogue of structured, source-backed specs per product, for any
category: laptops, USB-C wall chargers, power strips, eventually cars or non-electronics.
Audience: technically literate buyers comparing products on the facts marketing hides (e.g.
"does this charger support USB-PD PPS, at what voltage/current?", "which exact Yoga 7i config is
this?"). Tone: precise, trustworthy, dense but calm, like a well-made reference work. Not
a deals site, not a shop. Unknown is never shown as "no"; provenance (where a fact came from,
how sure we are) is a first-class part of the UI.
Read `ARCHITECTURE.md` section 0 (accepted design decisions) and `README.md` for context.

## What to build
1. `$impeccable init` equivalent: write `PRODUCT.md` yourself from this brief (you can't ask
   the user questions; this is non-interactive). Then design the visual system and write
   `DESIGN.md` (impeccable's file; our architecture doc is `ARCHITECTURE.md`, don't touch it).
2. A **category-agnostic data contract** for the static dataset, emitted by `scripts/build.py`
   into `docs/api/v1/`:
   - `categories.json`: list of categories, each with a field schema (key, label, group,
     type: number|bool|enum|text|range|list, unit, facet: yes/no, display priority).
   - per category: `products.json` (index rows for the listing), `products/<id>.json` (full record).
   - Generic record: id, category, brand, name, family/model/variant hints, identifiers,
     `specs` {key: value | {value, status: unknown|conflicted|not_yet_extracted, sources}},
     `media` (images), `documents` (manuals, spec sheets, links), `marketing_terms`, sources,
     confidence. Unknown/conflicted are explicit states.
   - Map the existing charger data (`data/gan-chargers/*.json`, old flat schema) into it inside
     build.py. Keep the old data files unchanged. Add a tiny hand-written **demo category**
     (e.g. 3-4 power strips, clearly marked `demo: true`) only to prove the UI renders a second
     schema; label demo data visibly in the UI.
3. The **UI** (static, GitHub Pages, served from `/specsheet/` subpath, so all URLs relative):
   - Home: category picker with counts.
   - Category view: schema-driven facet filters (generated from the category schema, not
     hard-coded), search across name/brand/identifiers, sortable comparison table with a
     column chooser, URL-encoded state, empty and loading states.
   - Product view: specs grouped by schema group, each value with source/confidence badge and
     explicit unknown/conflicted states; identifiers; documents and media sections (empty states
     now; the crawler will fill them later).
   - Compare: pick 2-4 products, side-by-side diff highlighting.
   - Works without a framework build step OR with one that outputs plain files into `docs/`
     (your call; justify it in DESIGN.md). Responsive, keyboard accessible, light/dark.
4. **Verification is mandatory** (the last version shipped with a JS syntax error that left the
   table empty): `scripts/build.py` must still syntax-check every shipped JS file with
   `node --check`, and add `scripts/smoke.mjs` that loads the built dataset and asserts every
   category/product JSON parses, every product's spec keys exist in its category schema, and
   counts match. If Playwright is available (`npx playwright`), also add a headless check that the
   category page renders > 0 rows and that searching "anker" in chargers returns > 0 rows.
   Serve locally with `python3 -m http.server -d docs` on port 3999 for tests.

## Process
1. Design: PRODUCT.md, DESIGN.md, data contract, page-by-page spec. Use `$impeccable shape`.
2. Spawn `sol_implementer` with the spec; it implements.
3. Spawn `astra_reviewer` to run `$impeccable critique` + `audit` on the result.
4. Send the ranked findings back to sol_implementer to fix P0/P1. Repeat at most twice.
5. Run all checks yourself and report.

## Constraints
- Do not modify `data/`, `raw/`, `crawler/`, `ARCHITECTURE.md`, `reviews/`. Another agent is
  building a crawler in `crawler/` concurrently.
- Do not commit or push. No external services, no analytics, no web fonts from third-party CDNs
  (self-host if needed).
- Final message: what was built, file list, check results, known gaps.
