# Brief: killer-query presets + interest instrumentation for the free deploy (PM round 2). Owner: A4. Read common.md, product/demand-survey.md §5, product/measurement-plan.md.
1. **Preset gallery on the home page**: 6-9 cards, one per killer query in demand-survey.md section 5. Each card shows the
   question in plain words, the result count, and opens the normal filtered table (URL-addressable, e.g. `?preset=ram-upgradable`).
   Presets are data in `docs/presets.json` {id, category, title, filters, columns, min_fill}. Do not hard-code them in app.js.
   A card renders only when the shown slice's fill for its filter keys is >= `min_fill` (default 0.8). Otherwise it shows
   "Help fill this: N of M known" and links to the request flow. Never show a confident-looking table that is mostly unknown.
2. **Unknown is first-class**: filters on a boolean/enum spec offer yes / no / **unknown** (unknown is never no). The result count
   splits "matches" from "unknown, might match". The product page shows the source link next to each core value, plus
   "maker claim" vs "verified (AHAM/regulator)" badges where a `*.verified_source` key exists.
3. **Special renderers**: the PDO table (power banks/chargers) as a small per-port table with a derived "Samsung 45 W: yes/no/unknown"
   pill. The TV family page gets a size × {panel type, zones, 4K120 HDMI ports} grid (it answers the panel lottery at a glance). The laptop
   config page gets a "Memory: 16 GB soldered + 1 free slot, max 48 GB" sentence generated from the mem.* keys.
4. **Beacons (UI side of measurement-plan.md)**: `killer_query` (preset id, result count), `source_click` (category, source
   domain), `request_click`, `spec_unknown_shown` (category, key; at most one per key per page view). Use `navigator.sendBeacon` to the
   api-worker endpoint the api agent exposes (/v1/event, or reuse /v1/miss). No cookies, no IDs, no product ids. While there is
   no Worker (GH Pages), the beacon is a no-op behind `BEACON_URL=null`.
5. **Agent parity**: the same presets are exposed as `GET /v1/presets` (static file is fine) and mentioned in llms.txt, so agents
   can discover the killer queries. Coordinate the endpoint with the api agent; its work is in pm-2026-11-24-api-gateway.md.
Accept: presets load from JSON, the min_fill gate works (test with a 0%-fill key such as flk.pwm today), the unknown filter is
on bool keys, and beacons are off when BEACON_URL is null. Report team/reports/2026-11-24-a4-killer-queries.md (<=60 lines). No deploys.
