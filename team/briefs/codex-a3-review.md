# Codex A3 review (gpt-6-astra, read-only)
You are A3 reviewer for ~/projects/specsheet. Read team/ROLES.md, ARCHITECTURE.md section 0 and 15,
schemas/*.json, team/reports/2026-11-22-a3-datamodel-v1.md (8 open questions) and
team/reports/2026-11-22-a3-impl-import.md, research/*/identity.md, crawler/adapters/_contract.py,
registry.py, scripts/import.py, scripts/v1_publish.py.
Context: pilots laptops (Lenovo PSREF ~1M MTMs all regions, ASUS, Apple) + power strips (Tripp Lite,
CyberPower, Jasco, Furman, Austere) are being collected; more categories (monitors, SSDs, robot vacuums,
routers, power banks, TVs, appliances, power stations) will follow, so the model must scale by adding
profiles + adapters, not code.
Deliver reviews/2026-11-22-astra-datamodel-v1.md: ranked findings (P0/P1/P2) with concrete fixes,
answers to the 8 open questions, identity/variant-grouping critique (esp. laptop config vs model, SSD
same-model-number component swaps = revisions), storage/publish scaling (static JSON size budget per
category, sharding), and a short list of changes to make before adding category #3. <= 250 lines.
Read-only: do not edit any file except that review.
