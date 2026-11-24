# specsheet agent team

Coordinator (Claude, main session): plans rounds, writes briefs, reads short reports, schedules
around usage limits (`~/projects/usage-limits/usage`), surveys categories. Agents hand off via files.

| Role | Owns | Typical model |
|---|---|---|
| A1 acquisition | `research/<cat>/spec-profile.yaml`: which specs matter, units, required, traps, where each spec lives | Claude Sonnet research; Codex Astra review |
| A2 discovery | `research/<cat>/manufacturers.yaml`, `research/<cat>/merchants.md`, parsers in `crawler/adapters/`, variant-grouping rules `research/<cat>/identity.md` | Claude Sonnet/Opus build; Codex review |
| A3 architect | `ARCHITECTURE.md` data model, `schemas/` (category profile format, record format), storage layout | Codex Astra design (Claude when Codex out); recurring re-review as categories grow |
| A4 frontend | `docs/` UI, `DESIGN.md`/`PRODUCT.md`, request + missing-search tracking | Codex Astra design, Claude/Sol build |
| A5 product manager | `product/`: monetization, pricing/tiers, licensing (code + data), hosting/storage of record, ToS/privacy, launch checklist, the decision log `product/decisions.md`; turns product decisions into briefs for A3/A4 | Claude Opus research + drafting; Codex Astra review of each plan |

Rules for every agent:
- Identity = manufacturer SKU / model number / MTM (e.g. Lenovo 83DK0002US), not retail listings.
  Retail titles are aliases only.
- Cheap collection: WebSearch + plain HTTP fetch. Bright Data only via coordinator approval
  (budget ~4200 credits; never Browser API, never bulk product pages).
- Never touch `raw/` contents destructively; never commit/push; write a report
  `team/reports/<date>-<role>-<topic>.md` (<= 60 lines, decisions + open questions first).
- Respect robots.txt, ~1 req/s per host.
