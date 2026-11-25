# Brief: doc parsers r3 (TV, router, laptop). Owner: A3-docs-2. Read common.md, team/reports/2026-11-24-doc-parsers-r2.md, team/reports/2026-11-25-doc-review6-fixes.md.
Goal: parse the remaining deferred documents (see coverage_audit / raw/_documents deferred list) for TVs (hdmi.has_4k120, HDMI 2.1 ports, panel/backlight, refresh), routers (radios/bands incl. 6GHz, wifi standard, ports), laptops (RAM soldered/slots/max, ports, USB-C PD/DP).
- Put new parsers in NEW modules (crawler/adapters/_docspec_tv.py, _docspec_router.py, _docspec_laptop.py) and register them with a minimal hook in scripts/docspec_attach.py. Another agent is editing crawler/documents.py and _docparse.py (OCR); do NOT edit those — if you need a hook there, describe it in the report.
- Identity binding per review-6 rules (row-scoped, model quoted, no sibling bypass). Affirmative-only; negatives only from complete enumeration with basis.
- New extractor ids, pending @N policies. Fixtures per category: one corroborate, one new fill, one wrong-model doc that must not attach.
- Fetch any still-unfetched deferred docs politely (robots, <=1 req/s, registered hosts only; list unlisted hosts in report).
Report: team/reports/2026-11-25-a3-docparsers-r3.md (<=50 lines): docs parsed, claims new vs corroborating, conflicts, preset fill deltas.
