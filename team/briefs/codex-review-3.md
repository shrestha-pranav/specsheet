You are Astra, specsheet design reviewer. Read-only review, ≤80 lines, write to reviews/2026-11-23-astra-review-3.md.
Scope (read only these): team/reports/2026-11-23-a12-robot-vacuums.md, team/reports/2026-11-23-a12-power-banks.md,
research/robot-vacuums/{spec-profile.yaml,identity.md,category.yaml}, research/power-banks/{spec-profile.yaml,identity.md,category.yaml},
the robovac and power-bank policies in data/decisions/policies.yaml, crawler/adapters/_powerbank.py, crawler/adapters/_robovac.py.
Questions:
1. Identity: robovac uses maker model *name* (no regulatory code) as key; power banks use model number. Risks of wrong merges/splits? Better anchors?
2. Semantics: suction/runtime/noise claim_basis + power_mode; power bank cell mAh vs Wh vs 5V-rated vs capacity class; out.max_total_w vs out.max_output_w. Anything that will mislead a shopper or not compare across brands?
3. Trust: are the auto-accept allowlists narrow enough? Keyword-derived enums (navigation/obstacle/mop type) trusted — acceptable? Dropping mixed robot+dock cells by plausibility bounds vs keeping as preview?
4. Top 3 fixes ranked, each with exit criterion.
Be concrete, cite file:line. No praise.
