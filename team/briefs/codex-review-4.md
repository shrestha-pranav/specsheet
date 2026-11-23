You are Astra, specsheet design reviewer. Read-only review, ≤60 lines, write to reviews/2026-11-23-astra-review-4.md.
Scope (read only): team/reports/2026-11-23-a12-tvs.md, team/reports/2026-11-23-a3-impl-r6.md, research/tvs/{spec-profile.yaml,identity.md,category.yaml}, scripts/bundles.py, the tvs + rel/bundle-contents policies in data/decisions/policies.yaml.
Questions:
1. TV identity: per-size model number as key, ENERGY STAR "same as basic model except designation" as the only alias-merge evidence, 90 proposals otherwise. ES wildcard families (OLED65C5***) are skipped: design a safe pattern->model relation (what may transfer: certification? power? never physical?).
2. ES-only entity vs site entity for the same set (QN65S90FAF vs QN65S90FAFXZA): merge rule or keep linked? Region-suffix handling.
3. Bundles: corroboration rule (title names member, all pages agree, not unit SKU, freebies dropped) — strict enough? Failure cases.
4. Top 3 fixes ranked with exit criteria. Cite file:line. No praise.
