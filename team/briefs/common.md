# Common context (all agents read this)
Project: ~/projects/specsheet (README.md = idea; ARCHITECTURE.md section 0 = accepted design decisions;
team/ROLES.md = team rules, follow them). Existing pilot: GaN chargers (data/gan-chargers, crawler/crawl.py
manufacturer-first crawler with Shopify/sitemap discovery, raw/ local store, gitignored).
Pilot categories this round: laptops, power strips (US market: US model numbers, NEMA plugs, UL ratings).
Identity: manufacturer SKU / model number / machine-type-model; retail listing titles are aliases only.

Provisional spec-profile format (A3 will formalize; stay compatible):
```yaml
category: laptops            # slug
version: 0.1
identity:
  levels: [family, model, configuration, package]   # adapt per category, explain
  primary_key: "what uniquely names a buyable configuration, per brand"
  per_brand: {lenovo: "MTM e.g. 83DK0002US", ...}
groups: [{id: cpu, label: Processor}]
specs:
  - key: cpu.model            # dotted, stable, lowercase
    label: Processor
    group: cpu
    type: number|bool|enum|text|range|list|object
    unit: W                   # SI/US unit or null
    enum: [...]               # if enum
    tier: core|important|detail   # core = needed to tell products apart / buy correctly
    facet: true               # filterable in UI
    why: "buyer reason"
    traps: ["how marketing hides/misstates it"]
    sources: ["where officially published: PSREF, spec page table, datasheet PDF, UL Product iQ, ..."]
    example: "Intel Core Ultra 7 258V"
```
Budget: WebSearch + WebFetch/curl only. No Bright Data. Write your report to team/reports/ (<=60 lines).
