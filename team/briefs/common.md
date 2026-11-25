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

Hard rules (classifier-enforced, do not retry if denied): no User-Agent spoofing, no curl/header workarounds against 403/Cloudflare/Akamai/WAF blocks, respect robots.txt. A blocked source gets recorded in merchants.md as blocked, then move on.
Never commit or push; never run `scripts/release.sh` without RELEASE_DRY_RUN=1. Coordinator releases.
Policies: new auto-accept policies need explicit source_ids/extractors/keys allowlists, a new @N id, and `approval: pending` (policy-lock.jsonl enforces immutability). Never edit a locked policy in place.
Other agents may be editing in parallel: keep shared-script edits (scripts/*.py, registry.py) minimal and list every shared-file change in your report.
Never run git stash/checkout/reset/restore in the shared working tree: parallel agents have uncommitted work. Compare against old output with `git worktree add /tmp/x HEAD` instead.
Builds: run bare import.py/build.py as `flock /tmp/specsheet-release.lock <cmd>`. release.sh takes that lock itself, so NEVER wrap release.sh in flock (deadlock).
Approvals: agents never fill approval.by/at. New policies land pending; the coordinator approves on the owner's standing authority (granted 2026-11-24) after review. Superseded versions move to retired_policies verbatim with a retired: {at, superseded_by, reason} line.
Fixtures that look like secrets (tokens, keys) must carry an inline '# gitleaks:allow' comment; CI runs gitleaks on every push.
