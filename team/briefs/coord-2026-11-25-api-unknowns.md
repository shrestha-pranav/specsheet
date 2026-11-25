# Brief: API returns unknown status. Owner: A3-api. Read common.md, team/reports/2026-11-24-api-gateway.md, team/reports/2026-11-25-a5-pm-round6.md item 5.
Coordinator ruling: the API must honour "explicit unknown + source". Unknown/conflicted/might-match state reveals no licensed value, so it is fine on all tiers.
1. api-worker/src/data.ts execQuery: results carry per-filter status (match | maybe(unknown) | maybe(disagree) | conflicted); a `include=maybe` param (default: matches only, but response always reports maybe counts). Detail responses list unknown core keys explicitly. Same semantics as scripts/presets.py (keep the TS/py parity test style: add fixtures).
2. MCP: add `list_categories_keys` (keys, types, units, facet, fill %) and `list_presets` tools; enable `match_product` if manifest match data exists in the pack (check why manifest match is null; fix pack builder if it's an omission).
3. Keep bounds (limit 25, batch 3, breaker 45k). Re-run CPU test; route matrix updated.
Files: api-worker/** only (+ pack builder script if needed; list it). Do not run release.sh. Report: team/reports/2026-11-25-a3-api-unknowns.md (<=40 lines). Deadline 12:00.
