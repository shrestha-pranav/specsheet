# A4: revisions UI + per-category copy (2026-11-23)
Edited: docs/app.js, docs/styles.css, scripts/frontend-smoke.mjs, DESIGN.md (index.html only via build.py hash).

1. Revisions: `revisionsMarkup()` renders "Hardware revisions" (before Documents) from model `revisions[]`: row per revision (label links to its page), only `differs` keys, value + "(model: x)" when the model differs, linked source-tier badge from the entry's local sources. Empty differs = "Nothing known beyond the model; hardware may or may not differ". Note "Specs above are for the default revision where a source shows a single version's table" shown only when a revision states a key the model lacks (beyond hardware_version). Revision pages (`kind=revision`, `variant_of`) get a "view the model and all revisions" banner. Generic over fields, so SSD/monitor swaps work.
2. Index rows with `kind=revision` are filtered out of trusted and preview listings (children, not products); no count/facet effect.
3. Preview copy: laptop-specific "e.g. Dell, Surface, Apple" removed. When `only_preview>0` brands are derived lazily from preview-only rows (loads the preview index after render, non-blocking); when 0 the text says it adds no new products.
4. Browser (390px, fresh ?r= load): all 6 categories + a product each render, 0 console/page errors, no "[object", no horizontal overflow. Revisions on routers/tp-link-archer-ax75 verified visually; fixed clipped first column on mobile.
5. Tests: frontend-smoke gained revisions test (one row/revision, badges, empty state, no revision rows listed). build.py, smoke.mjs, frontend-smoke.mjs pass.

Notes/data issues for coordinator: SSD product name shows a literal "™" escape (SANDISK Optimus GX PRO 850X NVMe™ ...). Browser had a stale cached app.js until a new URL was loaded (category-not-found for ssds/routers on old build). Preview details still do not list revisions. Brand hint costs an extra preview-index fetch on laptops (large). Not committed; screenshots deleted.
