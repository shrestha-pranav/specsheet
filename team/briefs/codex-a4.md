# Codex A4 frontend round (gpt-6-astra coordinator + sol_implementer)
Read team/ROLES.md, team/briefs/a4-contract.md, PRODUCT.md, DESIGN.md, docs/ (current UI),
reviews/ui-v1-critique.md. New real categories now published: laptops (US configs; per-port USB-C
lists; config vs model levels) and power-strips (real data; remove/hide the power-strips-demo category).
Tasks (use impeccable skill):
1. Make the UI handle these schemas well: object/list specs (per-port tables), tiers (core first,
   detail collapsed), model -> configuration drill-down for laptops (group configs under a model,
   show what differs), large categories (paginate/virtualize; lazy-load per-product files).
2. Missing-product + search-miss tracking on a static host: design + implement a privacy-preserving
   approach (e.g. "request this product" prefilled GitHub issue link + optional local queue), no
   third-party analytics. Document in DESIGN.md.
3. Fix remaining P1/P2 from ui-v1-critique.md.
Verification: python3 -I scripts/build.py (needs state/specsheet.sqlite, already built), node scripts/smoke.mjs.
Constraints: don't touch data/ raw/ crawler/ scripts/import.py ARCHITECTURE.md state/; no commits/pushes.
Final message: what changed, checks, gaps, which model each spawned agent ran on.
