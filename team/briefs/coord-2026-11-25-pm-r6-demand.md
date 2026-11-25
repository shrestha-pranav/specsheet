# Brief: PM r6 demand validation. Owner: A5. Read product/demand-survey.md, product/decisions.md D8, docs/api/v1/presets.json, product/launch-checklist.md.
Goal: are our 8 presets and core specs what real people/agents actually ask? Evidence-based, cheap (WebSearch, a few WebFetch; no Bright Data; no login-walled sites; respect ToS).
1. Sample recent public questions (Reddit buildapc/monitors/UsbCHardware/HomeNetworking/laptops via public search results, Stack Exchange super user, product Q&A on maker sites) for our 12 categories. Tally the spec filters people want (e.g. "USB-C 100W PD + 4K 144Hz monitor", "PPS 45W for Samsung", "DRAM SSD for PS5").
2. Rank top 15 unmet queries we could answer with our data; for each: needed keys, our fill today (read docs/api/v1 data), gap. Propose <=4 new presets and any to retire.
3. Agent use: what would an LLM agent call (MCP tool/API) — check our /v1 shape answers those queries in <=3 calls; list gaps.
4. Free-deploy readiness list for the "gauge interest" launch (owner said ~1 week): what must be true, what metrics (privacy-safe, D4) we capture.
Write product/demand-r6.md (<=80 lines) and report team/reports/2026-11-25-a5-pm-round6.md (<=40 lines). Do not edit code. Revenue stays on hold; don't propose account creation.
