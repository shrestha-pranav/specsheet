# Demand validation r6 (A5 PM, 2026-11-25)

Method: 15 WebSearch (standard), no Bright Data, no logins, no WebFetch of third-party pages (Reddit and Stack Exchange
terms restrict automated access, so they were used only through search snippets; neither surfaced threads directly,
same as r2). Evidence is snippet-grade [s]: buying guides, vendor blogs and forums (XDA, DIY Solar, HardwareZone,
Samsung Community). Fill = known / current maker-sourced rows in `docs/api/v1/<cat>/index*.json` on 2026-11-25
(an approximation of D8 scope; `presets.json` is the authority for the 8 shipped presets). "b" = brands with a value.
## 1. What people ask (tally of spec filters across the sample)
| Filter pattern people combine | Where seen [s] | Category |
|--|--|--|
| 27" + 1440p + 144 Hz+ (+ USB-C 90 W, + "flicker-free") | buying guides; ViewSonic VP2768a page | monitors |
| PPS **5 A** (not just "PD 45W") + 45 W port; cable e-marker | XDA, Samsung Community, vendor blogs | power banks |
| PS5: Gen4 x4, >= 5,500 MB/s, DRAM (PS5 has no HMB), **heatsink height <= 11.25 mm** | Tom's Hardware, TechRadar, PS5 guides | ssds |
| RAM socketed + USB-C PD charging wattage | upgradeable-laptop guides ("check the specific model") | laptops |
| 2.5G WAN + 2.5G LAN count, Wi-Fi 7, 6 GHz | Dong Knows Tech, Tom's Guide ("read the port table") | routers |
| **Per-port split** when 2 devices share a multi-port charger | UGREEN, charger guides (65+30 vs 60+30 vs 45+20) | chargers |
| Monitor USB-C PD watts actually delivered; KVM | KTC support blog (10 posts on it) | monitors |
| Robot height (under 3.5 in / 89 mm) + mop lift + self-empty | low-profile vacuum roundups | robot vacuums |
| UPS switchover ms + LiFePO4 (+ UL 2743) | DIY Solar, HardwareZone, Meh forums | power stations |
| Joules + VPR (330 V) + UL 1449 listed, not UL 1363 | HP, Home Depot, SPD guides | power strips |
| 4 x HDMI 2.1 at 4K120 (Sony Bravia 8 II / 9 II: only 2) | Tom's Guide, TechRadar, RTINGS lists | tvs |
| Filter cost/yr, filter life, noise dB | affiliate cost tables (they disagree) | purifiers |
| TLC vs QLC per capacity; "3D NAND" hides it | Newegg, Tom's Hardware, NAND guides | ssds |
## 2. Top 15 unmet queries (ranked by demand x how close our data is)
| # | Query | Keys | Fill today | Gap |
|--|--|--|--|--|
| 1 | 27"+ 1440p 144 Hz+ monitors | gen.size_class, res.native, res.refresh_max | 99/87/94% b3-4 | **none: 132 matches, no preset yet** |
| 2 | Robot vacuum fits under 3.5 in | phys.robot_height_mm | 87% b6 | none for height (23 match <= 89 mm); mop.lifting 40%, dock.self_empty 33% |
| 3 | LiFePO4 station >= 1 kWh | bat.chemistry, cap.energy_wh, out.ac_continuous_w | 85/82/91% b5 | none (28 match); ups.* in schema but 0% emitted |
| 4 | TVs with >= 4 HDMI at 4K120 | hdmi.ports_4k120 | 72% b3 (193 match) | shipped preset gates on has_4k120 (any port), not the asked ">= 4" |
| 5 | USB-C monitor, no PWM, PD >= 65 W | flk.pwm, usb.usbc_pd_w | 77/82% (preset) | flk.pwm 3 pts short; Dell/Philips/Acer/MSI/ViewSonic no maker source |
| 6 | Laptop USB-C: which port charges / DP / TB4 | port.usbc_list, port.tb_usb4, port.charge_port, port.video_out | **0%** | in schema, never emitted (PSREF publishes it): extraction bug, like mem.soldered was |
| 7 | PS5 SSD: DRAM + heatsink <= 11.25 mm | hw.dram_type, therm.heatsink(_height) | 67%; heatsink **0%** | heatsink keys never emitted; DRAM via D9.2 corrections |
| 8 | Power bank Samsung 45 W (PPS 5 A) | pd.pps, PPS range per port | 20%; range key absent for banks | Belkin support articles (D9); add per-port PPS range to power-bank profile |
| 9 | Surge strip: UL 1449, >= 2,000 J, VPR <= 400 V | type.ul1449_listed, surge.joules, surge.vpr_max | 62/71/62% **b2** | only 2 maker brands; APC/Belkin/Tripp Lite missing |
| 10 | Router: 2.5G WAN + Wi-Fi 7 | port.wan_speed_mbps, port.multigig_count | 57/23% | spec tables carry it; extractor coverage |
| 11 | Charger: power with 2 devices plugged | out.all_ports_w (as a split table) | 4% | needs a structured per-combination object, not a number |
| 12 | Monitor KVM / USB-C DP alt | usb.kvm, usb.usbc_alt_dp | **0%** (in schema) | extraction; Dell (the KVM brand) has no maker source |
| 13 | Station UPS switchover <= 10 ms | ups.supported, ups.switchover_ms | **0%** (in schema) | extraction; makers print it (EcoFlow "10ms UPS") |
| 14 | SSD TLC vs QLC at 2 TB | hw.nand_type | 40% (NVMe) | maker silence; corrections loop |
| 15 | Purifier filter cost/yr + noise | filter.price_usd, filter.life_months, noise.db | 0/0/38% of 29 maker rows | keys exist, unfilled; 29 of 1,142 rows are maker rows |
Pattern: #6, #7, #12, #13 are keys **in the profile, 0% emitted**: cheapest wins (same class as r2's mem.soldered).
## 3. Presets: propose (<= 4) and retire
Add (pass D8 on today's data by the measure above; presets.py must confirm):
- `monitor-1440p-144` "27-inch-plus 1440p monitors at 144 Hz or more" (size >= 27, res.native in 2560x1440/3440x1440,
  refresh >= 144; columns panel.technology, flk.pwm, usb.usbc_pd_w). Most-asked monitor query; shows PWM as a column, not a gate.
- `robovac-under-89mm` "Robot vacuums that fit under 3.5 in (89 mm)" (columns mop.lifting, dock.self_empty, nav.type, unknown shown).
- `station-lfp-1kwh` "LiFePO4 power stations with 1 kWh+" (columns out.ac_continuous_w, in.solar_w, ups.switchover_ms once filled).
- `surge-ul1449-2000j` held as "help us fill" (b2, 62-71%): ships when APC or Belkin lands.
- Change `tv-4-hdmi-4k120`: the id and the demand say ">= 4 ports", the title and gate say "any 4K120 port". Rename the title to match
  the gate now; switch the gate to `hdmi.ports_4k120 >= 4` when that key reaches 80% (72% today).
- Retire from showcase `power-bank-samsung-45w` (16%): take off the showcase row, keep as "help us fill" until the Belkin PPS fill lands. No other retirements.

## 4. Agent use: can /v1 answer each in <= 3 calls?
- Queries #1-5, #9-10: yes, 1 `query_specs` call **if** the agent already knows key names. MCP exposes only `query_specs` and
  `match_product`; key discovery means fetching static `schema.json` outside MCP. Gap: a `describe_category` tool (keys,
  units, enums, fill) or put the key list in the tool description.
- "Is the RAM soldered on 21ML003XUS?": `match_product` is not offered (manifest `match` is null), but
  `query_specs(q="21ML003XUS", fields="mem.soldered")` answers in 1 call.
- **Unknown is invisible in the API**: `execQuery` returns only `status == known` specs and filters drop unknowns. An agent
  asking for `flk.pwm` on a row where it is unknown gets the key silently omitted, and cannot get the "maybe" bucket
  presets already compute. This breaks our core promise ("explicit unknown plus source", r2). Fix: return requested fields
  with status (unknown / not_published) and an opt-in `include_unknown` so filters return yes + maybe with counts.
- No `presets` tool: an agent cannot ask "which ready questions are answerable" - expose presets.json via MCP (cheap).
- No compatibility check (laptop port x monitor PD): after #6 fills; not L1.

## 5. Free deploy ("gauge interest", ~1 week): what must be true
True now: repo public, Pages built, presets.json live (200), 5 of 8 presets pass. Must be true before announce:
1. Owner approves Terms/Privacy/Sources/About + DATA-LICENSE (step 11) - **owner blocker**.
2. Owner: Cloudflare account + `wrangler deploy` with PAYMENTS=off (steps 1, 4, 15); set `site.json` api_origin -
   without it the search-miss beacon is off and we measure nothing. **Owner blocker.**
3. Owner: enable GitHub Discussions (step 5; currently off) - the request/feedback channel.
4. Domain/email (steps 2-3, 17) can slip: `email_enabled=false` keeps GitHub links. Not a blocker for an interest test.
5. Agent: post-deploy route-matrix smoke (16), kpi.sql run (18), takedown drill (14), one-source restore (8).
6. Agent: the API returns unknown status (section 4) - else the agent demo contradicts the site.
Metrics (D4, privacy-safe, no IPs, no cross-day ids): daily page views (CF Web Analytics, cookieless); API/MCP calls per
route and tool; per-category filter **keys** (never values); search misses (redacted, k >= 3 to publish); preset card opens;
MCP clientInfo names on >= 3 days/week; Discussions/issue requests per week. Read-out after 7 days: which categories and
keys get queried, and the top misses -> next round's fill priorities. Calls measure use, not willingness to pay (D4).
