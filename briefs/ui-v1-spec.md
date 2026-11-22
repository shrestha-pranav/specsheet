# UI v1 implementation contract

## Scope and ownership
Implement `briefs/ui-v1.md` using PRODUCT.md and DESIGN.md. Allowed implementation files: scripts/build.py, scripts/smoke.mjs, additional scripts fixtures/helpers, docs/**. Do not modify data/, raw/, crawler/, ARCHITECTURE.md, reviews/, or existing user edits. Coordinator owns the design documents. No commits/pushes or external services.

## Data contract
`docs/api/v1/categories.json` is an array of `{id,name,description,count,demo,products,fields}`. `products` is relative to api/v1; fields are `{key,label,group,type,unit,facet,priority}` with type number|bool|enum|text|range|list, unit string or null, facet boolean, ascending display priority. Optional enum options and default-column metadata are allowed. Include machine-readable schema.json per category and a contract description in docs/api/v1/README.md or scripts documentation.

`<category>/products.json` is an array of index records carrying id, category, brand, name, identifiers, family/model/variant hints, demo, confidence and specs sufficient for filtering/sorting/comparison. `<category>/products/<id>.json` contains full generic records, including media (array), documents (array), marketing_terms (array), sources (array), notes and identity caveats. Detail and index identity/specs agree. Preserve old stable IDs where feasible; no model normalization that silently drops region/package differences.

Specs map schema keys to primitive typed values or `{value,status,sources,confidence,source_scope}`. Status vocabulary: known, unknown, conflicted, not_yet_extracted, not_applicable. Unknown states have value null; conflicted may retain literal candidate text plus explanatory notes, but is excluded from numeric/boolean filtering as established fact. Sources reference the record source IDs. Each source has id,url,label and optional kind. Confidence retains original record scope; absent field evidence must be labeled unverified/record context, not invented. List [] is known empty only when explicitly documented; legacy empty lists that mean uncollected should be unknown and explained by adapter policy. Null becomes unknown. Missing keys become not_yet_extracted. Preserve notes, literal ranges, port conditions and ambiguous identity hints; do not resolve uncertain model equivalences. Flag explicit conflict prose (e.g. Anker A2697 weight, A2687 single-port power, contradictory cable contents) conservatively in adapter, with notes retained.

Map legacy charger facts in build.py, never alter input. Include all relevant specs in schema (port lists, PPS ranges, power sharing, dimensions, protocols etc.); price fields if retained are historical observations, not price filters or current offers. Brand filter can be shared generic identity filtering. Add 3–4 clearly fictional demo power strips under scripts/ fixtures or inline builder data, with bool, number, enum, text, range and list examples and unknown/conflicted/not_yet_extracted examples. Demo fields must differ from chargers. Every demo view has a visible Demo data label.

## Page and state specification
- Home `#/`: compact catalogue introduction and category rows with counts, demo label on demo category, static dataset link and pilot explanation.
- Category `#/category/<id>?...`: search name/brand/all identifier values; facets generated strictly from schema, with type-appropriate controls (numbers/ranges min/max, bool Any/Yes/No/Unknown, enum options, text/list matching). Unknown/conflicted never pass established true/false or numeric criteria. Sort headers are buttons with aria-sort; unknowns sort last. Column chooser lists schema fields; identity columns remain. Serialize query, filters, sort/direction, chosen columns and selected IDs into URL; reload/back/forward restore them. Provide reset filters, result count, zero-results recovery, loading and fetch error/retry states. Search must retain focus and caret while updating.
- Product `#/product/<category>/<id>`: grouped specs from full record, source and confidence affordance for every value, identifiers with scope/raw values, family/model/variant hints explicitly unverified where appropriate, marketing terms separated, notes, documents/media with empty states. Handle bad URLs/missing product with useful recovery.
- Compare `#/compare/<category>?ids=...`: same-category 2–4 selections, grouped schema rows, diff highlighting and differences-only control, clear remove/back actions; invalid selection has recovery. Category selection shelf is keyboard accessible and never obscures content.
- Theme: light/dark/system control, persists locally; storage denial must not break app. All internal asset/data URLs relative. Route builders encode identifiers safely.

## Direction contract
THESIS: Make evidence inspectable while keeping comparison dense and calm.
OWN-WORLD: Cool mist/slate surfaces, teal actions, compact system typography and ruled tables.
STORY: Choose category, narrow factual attributes, select products, inspect differences, trace evidence.
FIRST VIEWPORT: Compact masthead and category heading; filter rail at left, search and count over a filled table at right; first products visible without scrolling on desktop. Mobile puts a filter disclosure above the table.
SIGNATURE: Every detailed value has an adjacent evidence affordance that distinguishes direct sources from record context; selection highlights link catalogue rows to a named comparison shelf.
MOTION: Immediate stable filtering, small selection tint transitions, reduced-motion support. No decorative entrances.

## Acceptance
python3 -I scripts/build.py; node scripts/smoke.mjs. If Playwright CLI/package is available, add headless checks and run them against `python3 -m http.server 3999 -d docs`. Check >0 charger rows and >0 rows for anker, both demo and real schema rendering, state round-trip, comparison, phone and desktop light/dark captures. Build must not depend on Playwright to distribute static files.
