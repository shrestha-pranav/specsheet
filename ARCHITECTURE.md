# specsheet — design plan v0.2 (2026-11-22)

Status: v0.1 reviewed by GPT-6-Astra (`reviews/2026-11-22-astra.md`); accepted changes in section 0,
which **overrides** the sections below where they conflict. Owner of the idea: README.md. Pilot data: data/gan-chargers/.

## 0. Review outcome (accepted 2026-11-22)

1. **Identity before publication.** Entity resolution moves from phase 3 to phase 0. Uncertain
   crosswalks (e.g. ChargerLAB CN code ↔ US SKU) are `possible_match` relationships; claims derived
   through them are not published as accepted specs.
2. **Data model adds package and listing.** Family (browse only, no auto-inherited electrical
   specs) / model / configuration / **package** (single, multipack, bundle; own GTINs) / **listing**
   (one source's view) / optional evidenced **revision**. Explicit-unknown or conflict blocks inheritance.
3. **Relations, not merges.** `same_configuration`, `same_package`, `variant_of`, `member_of_family`,
   `contains`, `possible_match`, `different`, `insufficient_evidence`. Only equivalences are
   transitive. Low-score observations stay unresolved instead of minting entities. Nontrivial links
   are **human-approved** at this scale; LLMs rank and summarise, never authorise merges.
4. **Matching rule fixes.** Don't strip multipack/generation/region tokens: parse them into
   features. Don't normalise away regional suffixes. FCC ID is *not* a hardware-equivalence key
   (shared radio modules). Missing specs are not agreement. Identifiers are scoped
   (issuer, scheme, market, package level), raw value preserved, GTIN check digits validated.
5. **Field-directed extraction** replaces "stop at first rung": run stages until the *target
   fields* have evidence, the source is exhausted, identity is ambiguous, budget is out, or access
   is blocked; store the stop reason (`not_found` ≠ `not_attempted`). **OCR of spec images is a
   core path**, with image-hash dedupe and literal-text preservation (Anker `3..25A` is stored
   literally + a proposed normalisation, not silently "fixed"). No synchronous OCR/browsing from
   public queries.
6. **Change detection uses several fingerprints**: raw hash, spec-section hash, asset manifest
   (image/PDF hashes), variant fingerprint. Extraction cache key includes content hash + schema +
   adapter/prompt + model version. Discovery is checkpointed; a partial or blocked enumeration never
   marks products discontinued.
7. **Source policy per source**: automated access allowed?, raw retention (Best Buy API terms cap
   caching at 72 h, so "keep snapshots forever" is dropped as a universal rule), may content go
   to an LLM provider, republication, commercial redistribution. Publish normalised facts + links;
   raw evidence stays private. No proxy rotation / CAPTCHA circumvention.
8. **Claims carry conditions and kind**: `declared | negotiated | measured | derived`, plus
   port/active-ports/input-voltage conditions. Measured does not overwrite advertised (sustained vs
   peak). Resolver may return `conflicted`. Confidence splits into identity / extraction / evidence.
   Source independence tracked (3 retailers copying one blurb = 1 origin).
9. **Absence semantics**: `unknown`, `not_applicable`, `conflicted`, `not_yet_extracted`; an empty
   list means "known empty".
10. **Laptops**: MTM-level fixed configs only as documented; CTO options stored with constraints,
    never a Cartesian product; incomplete retailer configs stay ambiguous; retailer RAM/SSD
    upgrades are distinct from factory configs. PSREF does not enumerate CTO.
11. **Backend v1 = FastAPI + Postgres** (JSONB append-only claims + typed resolved projections),
    one worker on leased Postgres jobs, private object storage. Not Workers + D1.
12. **v0 is a "static dataset distribution", not an API**: versioned releases, manifest,
    per-entity JSON, ID alias/tombstones. API keys arrive with the dynamic API (hashed keys,
    scopes, per-key burst + per-account quota, usage records). GitHub Pages forbids commercial
    SaaS, so paid service must move hosts.
13. **Crowd v1 = correction reports + maintainer review** (`submitted → needs_evidence →
    accepted/rejected → superseded`); acceptance creates a claim, never edits a resolved value.
    No reputation weighting yet. Hardening (review-7, 2026-11-25; mechanics in `scripts/corrections.py` docstring):
    an accept binds to a content digest of the claim (an edited issue is withheld until decided again); deciders
    must be listed in `data/decisions/maintainers.yaml` (public maintainer handles: the one documented exception to
    "no personal data"); every string and evidence URL is sanitized (decoded PII, tokenised query params) before
    `data/corrections/` is written; every fetch and redirect hop is policy-checked, with one narrow **intake
    exception**: hashing images a contributor attached to a field-correction issue (GitHub attachment hosts/CDN,
    bytes hashed in memory) although github.com issue pages are `crawl: human_only`.
14. **Cut from v1**: Dell/HP + broad laptops, LLM merge adjudication, reputation voting, paid
    unblocking, regulatory-wide discovery, user-triggered deep extraction, price filters/history,
    billing. **Not cut**: OCR, per-field evidence, package separation, unresolved identity states,
    reversible decisions, conditional specs, review tooling.

**Revised phases** (replaces section 10):
0. Repair pilot: enforceable JSON Schema, stable IDs, package/config split, disputed links isolated,
   no placeholder identifiers.
1. Prove acquisition economics on 3 brands (Shopify-structured, image-heavy, manual-backed):
   measured cost + review minutes per accepted field; fixtures for unchanged / image-changed /
   blocked / delisted.
2. Publish v0 static catalogue with PPS filters + evidence display + issue-based corrections.
   Acceptance query: "US-plug chargers with a documented PPS profile ≥ 3 A across a given voltage range".
3. Dynamic v1: FastAPI/Postgres, incremental jobs, moderation, keys + quotas.
4. Laptop identity on one Lenovo family (e.g. 2026 Yoga 7i), fixed configs, limited CTO.
5. Expand / monetise once demand + source rights justify it.

## 1. Goal and scope

A catalogue of **structured, sourced, comparable specs per purchasable product variant**,
across brands, for categories where marketing names hide the facts that matter
(GaN chargers: PPS ranges, per-port power and how it splits; laptops: CPU/RAM/panel per config).

v1 deliverables, deliberately small:
- **Read API** (JSON over HTTP): search, filter by spec, get one product with field-level provenance.
- **Simple UI**: category table with facet filters, product page showing every field with
  its source + confidence, and a "this is wrong" form.
- **Ingestion pipeline** that keeps the data fresh cheaply.
- API keys with per-key rate limits from day one (so a paid tier later is a billing switch,
  not a redesign). No payments in v1.

Non-goals for v1: price tracking/deals (separate system exists: bf-deals), reviews, user accounts
beyond an email-verified contributor identity, mobile app.

The two hard problems this design is mostly about:
1. **Efficient, trustworthy acquisition** from sources we trust.
2. **Identity**: deciding when two listings are the same product, a variant of it, or different.

## 2. Data model

Three levels, because "the product" means different things to different sources:

| Level | Meaning | Charger example | Laptop example |
|---|---|---|---|
| **Family** | Marketing name, a product line generation | Anker Nano Charger (65W) | Lenovo Yoga 7i (2026, 14") |
| **Model** | One hardware design, one spec set *except* configurable axes | A2663 | Yoga 7i 14ILL11 (machine type 83xx) |
| **Variant (SKU)** | One purchasable configuration | A2663 black US plug | 83xx001xUS: Core Ultra 7 258V / 16 GB / 1 TB / 2.8K OLED |

- Specs attach at the **lowest level where they vary**. Inherited downward; a variant stores
  only its deltas (colour, plug, RAM, CPU...). The UI shows a family as a **variant matrix**
  (axes = the fields that differ), which is what makes the laptop case tractable.
- **Identifiers** table: `(entity_id, scheme, value, source_id, first_seen, last_seen)` with schemes
  `brand_model`, `brand_sku`, `mtm` (Lenovo machine type model), `upc`, `ean`, `gtin`, `asin`,
  `fcc_id`, `retailer_sku:<store>`. Identifiers are the backbone of matching (section 4).
- **Claims, not columns-of-truth.** Every fact is a row:
  `claim(entity_id, field, value, unit, source_id, extracted_at, extractor, method, raw_snippet_hash)`.
  The displayed value is a **resolution** computed from claims (section 5). This gives provenance,
  lets crowd input be just another source, and makes re-extraction idempotent.
- **Category schemas** are versioned JSON Schema per category (`gan_charger@1`, `laptop@1`),
  with per-field: type, unit, canonicalisation rules, which level it normally lives at, and
  whether `null` (unknown) is allowed. Unknown is never displayed as "no".
- Storage: Postgres (JSONB for values, pg_trgm for fuzzy names). SQLite is fine for the pilot.

## 3. Acquisition: getting data cheaply from trusted sources

### 3.1 Source registry and trust tiers
Each source has a tier, which drives both crawl priority and conflict resolution:

| Tier | Source type | Examples | Use |
|---|---|---|---|
| T0 | Regulatory / standards | FCC ID filings (test reports, user manuals), USB-IF certified product list, UL Product iQ, Energy Star | identity + hard specs; very stable |
| T1 | Manufacturer | brand product pages, spec tabs, manual/datasheet PDFs, PSREF (Lenovo), Dell/HP spec sheets, brand JSON endpoints | primary specs |
| T2 | Independent measurement | ChargerLAB tests/teardowns, Notebookcheck reviews | measured values; overrides T1 when it disagrees with evidence |
| T3 | Retailers | Best Buy, Amazon, B&H, Newegg | identifier bridging (UPC/ASIN ↔ model), prices, availability; low trust for specs |
| T4 | Crowd | contributor submissions with evidence | fills gaps, flags errors; promoted by moderation |

Trust is per (source, field), not just per source: e.g. Amazon titles are bad for PPS but fine for
colour; manufacturer pages can be wrong on PPS ranges where ChargerLAB measured them.

### 3.2 Discovery (what exists) vs extraction (what it is)
- **Discovery** enumerates entities cheaply, without reading spec pages:
  brand `sitemap.xml` / product-feed / Shopify `products.json` (many charger brands run Shopify:
  structured variants + SKUs for free), category listing pages, PSREF model lists, FCC grantee code
  listings (new filings appear months before launch), USB-IF list deltas.
- **Extraction** reads one page/PDF for one entity.
- Separating them means a daily discovery pass is a handful of small requests, and extraction
  only runs on new or changed pages.

### 3.3 Extraction ladder (cheapest first, stop at the first rung that yields valid data)
1. **Structured data in the page**: schema.org `Product` JSON-LD, Open Graph, Shopify variant JSON,
   embedded `__NEXT_DATA__`/hydration JSON. Deterministic, free, no LLM.
2. **Per-site deterministic adapters** (CSS/XPath or JSON paths) for high-volume sources
   (e.g. PSREF tables, Anker/UGREEN spec tabs). Written once, maybe LLM-generated, then frozen
   and tested on fixtures; an adapter that starts failing validation is quarantined, not trusted.
3. **LLM extraction** to the category schema for the long tail: feed cleaned text (readability,
   tables kept as markdown), not raw HTML; small model first, escalate to a bigger one only when
   schema validation fails or confidence is low. Output must quote the snippet each value came
   from; values without a matching snippet in the source text are dropped (anti-hallucination).
4. **Images** (spec tables in listing JPGs, common for PPS ranges): OCR → LLM, only for fields
   still null after rungs 1-3, and only for entities someone actually views or queries (lazy).
5. **Headless browser**: last resort, only for sources that need JS, budgeted per day.

### 3.4 Cost and politeness controls
- HTTP conditional requests (`ETag` / `If-Modified-Since`), store raw responses content-addressed
  (hash → blob) so re-extraction after a schema change costs zero fetches.
- **Change detection on the cleaned text hash**, not the raw HTML (ads/timestamps churn).
- Recrawl cadence by tier and volatility: T0 rarely, T1 weekly, prices daily, discontinued monthly.
- Per-domain rate limits, robots.txt honoured, identifying User-Agent; prefer official feeds and
  APIs (Best Buy has a public product API with UPC + specs) over scraping retailers.
- Daily spend budget for LLM calls + any paid fetch, enforced before the call.
- Demand-driven depth: the long tail is discovered but extracted at low depth until someone queries it.

## 4. Entity resolution: is this the same product?

The core matching pipeline runs on every new **observation** (one source's view of one product):

1. **Normalise**: brand aliases (EF EcoFlow → EcoFlow), units (65 W, 65W, 65-Watt), strip noise
   tokens from titles ("[2-Pack]", "Upgraded", "for iPhone 16", colour words, "2026 newest").
2. **Hard-key match** (decides most cases): exact match on strong identifiers, in order:
   UPC/EAN/GTIN → brand model/SKU (normalised: case, dashes, regional suffixes per brand rules) →
   Lenovo MTM / Dell service config / HP product number → FCC ID (same FCC ID = same hardware, but
   possibly several models) → ASIN (retailer-scoped, can be *reused* or merged by Amazon — weak).
3. **Blocking + soft match** when no hard key: block by (brand, category, headline spec, e.g.
   wattage), then score candidates on name similarity (token-set, with model-code tokens weighted
   high), spec-vector agreement, and image perceptual hash. Contradicting a *defining* spec
   (wattage, port count, CPU) is a hard veto regardless of name similarity.
4. **Decide**: high score → auto-link; mid → LLM adjudication with both records side by side,
   which must answer `same_variant | same_model_different_variant | same_family | different` with
   a reason; low → new entity. Every link stores its method and score and is reversible
   (merges are events, not overwrites), so a bad merge can be split later without data loss.
5. **Variant placement**: once linked to a model, the observation's differing fields decide
   whether it is an existing variant or a new one. Category schema marks which fields are
   **variant axes** (charger: colour, plug, bundled cable; laptop: CPU, RAM, storage, panel, GPU,
   OS, colour) and which are **model-defining** (if they differ it's a different model).

Specific traps to design for:
- **Same name, different hardware**: "Anker Nano 65W" exists as several generations (Nano II 65W
  A2663 vs Nano Charger 65W A2xxx). Model code beats name; generation/year is a model-defining field.
- **Same hardware, many names**: retailer-exclusive names (Costco bundles, Walmart editions),
  regional codes, colour suffixes. Linked via shared model code, FCC ID or UPC.
- **Bundles / multipacks**: a bundle is its own entity that *contains* N components (with qty);
  the components link to their own models. Prevents "2-pack" polluting single-unit specs.
- **Laptops (e.g. 2026 Yoga 7i)**: family = "Yoga 7i Gen 11 14\"" (Intel vs AMD = separate models
  if the MTM prefix differs), variants = MTM-level configs. Seed from PSREF (manufacturer variant
  matrix); retailer listings attach by MTM in the listing or, failing that, by exact config
  vector (CPU+RAM+storage+panel) inside the family. "Customise-to-order" configs are represented
  as the model's axis option sets rather than enumerated variants.
- **Silent revisions**: same model code, changed internals (e.g. new PPS range in a later batch).
  Handled as a `revision` sub-level only when evidence exists (dated test, FCC permissive change).
- **ASIN drift**: Amazon merges or reuses ASINs; ASIN links decay and are re-validated.

Evaluation: a hand-labelled gold set (~300 observation pairs for chargers, ~300 for laptops),
precision/recall reported on every matcher change. Optimise for **precision** (a wrong merge
corrupts specs; a missed merge is just a duplicate, which users can flag).

## 5. Conflict resolution and confidence
- Resolved value per field = highest-trust claim, with recency as a tie-break, except: a T2
  measured claim with evidence beats T1; T4 crowd claims need N independent confirmations or
  moderator approval before they can beat T1.
- Show conflicts rather than hiding them (`PPS: 3.3-11V 5A (Anker page) · measured 3.3-11V 4.2A
  (ChargerLAB)`).
- Confidence: high (T0/T1 + agreeing source), medium (single T1 or T2), low (T3, inferred, LLM-only).

## 6. Crowd contributions
- Contributor identity: email-verified account (later OAuth). Each submission = claim + evidence
  (URL, photo of label, meter screenshot). Evidence images get OCR'd and checked against the claim.
- Reputation: accepted submissions raise weight; reversed ones lower it. Moderation queue for
  anything changing a model-defining field or overriding T1.
- Abuse: rate-limited per account/IP, brand-affiliated accounts flagged.

## 7. API (v1)
- `GET /v1/categories`, `GET /v1/categories/{cat}/schema`
- `GET /v1/products?category=gan_charger&filter=pps:true,max_single_port_w>=65,ports>=2&sort=...`
- `GET /v1/products/{id}` (family/model/variant, resolved fields + `provenance` per field)
- `GET /v1/lookup?upc=|model=|asin=|mtm=` (the identity-resolution service as an API: likely the
  most valuable paid endpoint)
- `POST /v1/submissions` (contributor auth)
- API keys, per-key quotas, usage metering table from day one; free tier small. Stable IDs (ULIDs),
  never reused, and merged IDs redirect.

## 8. UI (v1)
Server-rendered pages (or a thin SPA over the API): category table with facet filters,
product page with a variant matrix and per-field source badges, "suggest a correction" form,
contributor sign-in, moderation page. No design system beyond flat, readable tables.

## 9. Architecture
- Python: `fetcher` (queue, politeness, cache, conditional GET) → `extractors` (ladder) →
  `observations` → `matcher` → `claims` → `resolver` (materialised resolved view) → API (FastAPI)
  + UI. Jobs on a simple Postgres-backed queue; no Kafka.
- Everything re-derivable from raw blobs + claims: resolver and matcher are pure functions that
  can be re-run.
- Pilot runs on the home server; public hosting later. LLM calls through one wrapper with
  budget enforcement and caching by (prompt hash, model).

## 10. Phases
1. **Pilot (now)**: chargers, 9 brands, agent sweep to JSON (done-ish), gold set, merge checks.
2. **Pipeline**: fetch cache + discovery for 3 brands (Shopify JSON + sitemaps), JSON-LD + adapter
   extraction, claims + resolver, read-only API + table UI.
3. **Identity**: matcher with hard keys + soft match + LLM adjudication, gold-set evaluation, bundles.
4. **Laptops**: PSREF-seeded Lenovo, Dell, HP; variant matrix UI.
5. **Crowd + API keys + metering**, then paid tier.

## 12. Pilot results (2026-11-22 sweep, 9 brands)

150 SKUs (Baseus 36, UGREEN 33, Anker 22, Belkin 18, Satechi 10, Spigen 9, CUKTECH 8,
EcoFlow 7, INIU 7). PPS confirmed for 69, **unknown for 77**, exact PPS ranges for only **29**.
63 records are low confidence. Collected by 5 LLM agents in ~5-15 min each (~620k subagent tokens).

What the pilot taught:
- **Shopify `products.json` is the best discovery source**: Baseus, INIU, UGREEN, EcoFlow, CUKTECH
  all run Shopify; one plain `curl` returns every product + variants + SKUs + prices. LLM-free.
- **Brand pages hide the key spec in images.** UGREEN US and newer Baseus pages carry per-port
  watts / PPS only in JPG spec tables, so rung 4 (OCR) is not "rare": it is the main path for
  the field users care about most.
- **ChargerLAB is the best source for PPS ranges** but agents often got only intros
  (truncated/JS); needs a proper adapter, and its CN/global model codes (e.g. UGREEN X774, Anker
  A2669) must be mapped to US SKUs: that mapping was name + port-count guessing in the pilot,
  i.e. exactly the identity problem.
- **Anti-bot + rate limits**: Amazon 503 throughout, WebFetch 429s on baseus.com/iniushop.com,
  B&H 403. Retailers are not a viable spec source without paid unblocking; use official APIs
  (Best Buy) or skip.
- **Delisted products vanish** (Spigen removed all chargers; Belkin/EcoFlow US 404s). Raw snapshots
  must be kept forever, and "status" needs evidence (last-seen-on-official-store date).
- **Typos and contradictions are common in T1 sources** (Anker support "3..25A"; Belkin chart 96W
  vs 140W measured; UGREEN 8-port vs 5-port): the claims/conflicts model is required, not optional.
- **Prices are noisy** during sales (store list vs promo vs feed); price is a separate, volatile
  series, not a spec field.
- **Placeholders leak** ("UNKNOWN" as a model number caused a false duplicate): validators must
  reject them at ingestion.
- One genuine duplicate model number across records (INIU `A12-E1`: single vs 2-pack listing)
  is the bundle case from section 4.

## 13. Hosting, v0 → v1

- **v0 (now)**: GitHub repo; `scripts/build.py` turns `data/**.json` into a static site + static
  JSON "API" under `docs/` (GitHub Pages). Corrections = GitHub issues. Zero cost, zero servers.
  The data files are the database; PRs are the moderation queue.
- **v1**: when we need write paths (submissions, API keys, metering), move to a single small
  backend: e.g. Cloudflare Workers + D1 (SQLite) or a FastAPI app + Postgres (Supabase/Neon free
  tier). Static site keeps working as a cache/CDN of the read path. Key question for review: which.

## 14. Open questions for review
- Is the 3-level family/model/variant enough, or do we need explicit `revision`?
- Claim store in Postgres JSONB vs a typed column per field per category?
- LLM adjudication for mid-score matches: worth it, or just queue for humans at this scale?
- Legal/ToS: storing manufacturer text vs facts only; retailer scraping vs official APIs.
- What's the minimum gold set size to trust auto-linking?

## 15. Data model v1 (A3, 2026-11-22; pending Codex review)

Formal schemas: `schemas/category-profile.schema.json`, `schemas/record.schema.json`,
`schemas/units.json`. Section 0 still overrides; this section makes it concrete. Frontend contract:
`team/briefs/a4-contract.md`.

### 15.1 Three layers, one direction of flow

```
adapters ──► RAW (local, immutable)  ──►  NORMALIZED (git: data/)  ──►  PUBLISHED (git: docs/api/v1)
             snapshots + blobs            entities + claims + relations    resolved, stripped, static
             state/specsheet.sqlite       research/<cat>/spec-profile.yaml
             (working index, derivable)   data/sources.yaml
```
Every layer is re-derivable from the one to its left plus human decisions (approved relations,
claim reviews), which live only in `data/` and are therefore never lost by a rebuild.

### 15.2 Category profiles
`research/<cat>/spec-profile.yaml` (A1 owns content; A3 owns format). The provisional format is
valid v1; additions are optional: `profile_format`, `units` (canonical unit per spec; market
display units, e.g. m→ft for US cords), top-level `conditions` dimensions (port, active_ports,
input_voltage, mode...) that specs opt into, `items`/`fields` for per-instance lists (ports,
outlets), `headline_condition` (which conditioned value is the table/facet value), `level` +
`identity_role` (variant_axis / model_defining), facet objects (`kind`, `path`, `bins`,
`column`, `unknown_bucket`), `derived` specs, key `aliases` for renames. Spec keys are permanent;
a retype or re-unit is a MAJOR profile version and publishes as a new `schema_version`.

### 15.3 Entities, identifiers, claims
- **Kinds**: family / model / configuration / package / listing / revision; one file each.
  Links are `relations` with `status` proposed|approved|rejected|retracted; only approved
  relations feed resolution, `possible_match` never transmits claims, family never passes specs
  down. Inheritance is model → configuration → package, blocked by an explicit claim at the
  lower level (unknown/not_applicable/conflict included).
- **IDs**: readable slugs `<brand>-<primary identifier>[-qualifier]`, globally unique, minted
  once, never reused. Merge/split = tombstone `data/_ids/tombstones.jsonl` (`{id, replaced_by[], at,
  reason}`) → published `redirects.json`.
- **Identifiers** are namespaced (`mfr_model`, `mfr_sku`, `mtm`, `gtin`, `fcc_id`, `ul_file`,
  `retailer:<store>`), keep `value_raw`, carry issuer/market/package_level and `role`. `retailer:*`
  (incl. ASIN) and `fcc_id` are schema-forced `role: alias`: pointers, never hard keys.
- **Aliases**: retail titles, marketing/regional names: searchable, never identity.
- **Claims** (append-only): `{key, status, value, unit, raw, conditions, kind, measurement, source,
  locator, quote, method{stage, extractor@version, model, cache_key}, observed_at, review}`.
  `kind` = official | measured | derived | reported (§0.8 "declared" = official; negotiated/sustained/
  peak = `measurement.mode`). Claim ids are content hashes, so re-running an extractor is a no-op.
  Claim status known | unknown | not_published | not_applicable; `conflicted` and
  `not_yet_extracted` exist only on resolved specs. Extraction stop reasons go in `absences`.

### 15.4 Storage layout
| Path | Git? | Contents |
|---|---|---|
| `raw/<source>/snapshots.jsonl` | no | **Append-only** snapshot log: `{snapshot: sha256:<body>, ref, url, final_url, status, fetched_at, etag, last_modified, adapter@ver, blob}` |
| `raw/<source>/blobs/<sha256><ext>` | no | Content-addressed bodies (HTML gz, JSON, PDF, images). Never overwritten, retention per `data/sources.yaml` |
| `raw/<source>/index.jsonl`, `products/<key>/*` | no | crawl.py v0 "latest view" (kept; becomes a cache derived from snapshots) |
| `state/specsheet.sqlite` | no | Working store: refs, discovery checkpoints, observations, *candidate* claims, extraction cache, OCR queue, search-miss/request intake. Deletable: rebuilt from raw + data |
| `data/sources.yaml` | yes | Source registry + policy (§0.7): tier, automation_ok, retention_h, llm_ok, republish |
| `data/<cat>/<kind>/<id>.json` | yes | Normalized entity records (record.schema.json) with **accepted** claims, approved/rejected relations, identifiers, aliases. Diffs = review |
| `data/_ids/tombstones.jsonl` | yes | Retired ids |
| `data/gan-chargers/<brand>.json` | yes | v0 pilot input; migrated by a one-off importer (`method.extractor: legacy-pilot@0`, `review: candidate`) |
| `docs/api/v1/**` | no (gh-pages) | Published static dataset (build output): published as a single orphan commit on `gh-pages` by `scripts/release.sh`, never committed to main; `releases/<id>.json` (main) is the manifest |

crawl.py today overwrites `page.html.gz`/`extract.json` on `--refresh`; v1 adapters must
additionally write the snapshot log + blob so history is immutable. Per-source blob stores are
fine (dedupe across sources is not worth a migration). Promotion `state → data/` is a script
(`scripts/promote.py`, to build) that writes only claims that validate against the profile and
entity creation/links that are hard-key or human-approved; the git diff is the review.

### 15.5 Adapter contract (every A2 adapter, `crawler/adapters/<id>.py`)
```python
@dataclass(frozen=True)
class Ref:            # something discoverable at a source
    source_id: str; key: str; url: str
    hints: dict       # title, skus, gtins, product_type, feed blob... (cheap, unverified)

@dataclass(frozen=True)
class Discovery:
    refs: list[Ref]; complete: bool; stop_reason: str | None   # only complete=True may mark gone
    checkpoint: dict  # opaque, passed back on the next run

@dataclass(frozen=True)
class Snapshot:
    snapshot: str     # "sha256:<hex>" of body; blob path derived
    ref: Ref; status: int | str; fetched_at: str; final_url: str
    headers: dict     # etag, last_modified, content_type
    not_modified: bool = False   # 304 -> points at the prior snapshot

@dataclass
class ParseResult:
    identifiers: list[dict]; aliases: list[dict]; claims: list[dict]   # record.schema $defs shapes,
    media: list[dict]; documents: list[dict]; absences: list[dict]     # entity unresolved
    links: list[Ref]  # follow-ups: PDFs, spec images, variant pages
    fingerprints: dict   # raw, spec_section, assets, variants (section 0.6)

class Adapter(Protocol):
    id: str; version: int; source_id: str          # bump version => extraction cache miss
    categories: set[str]                           # profiles it can emit claims for
    def discover(self, checkpoint: dict | None, net: Net) -> Discovery: ...
    def fetch(self, ref: Ref, prior: Snapshot | None, net: Net) -> Snapshot: ...
    def parse(self, snap: Snapshot, blobs: BlobReader, profile: Profile) -> ParseResult: ...
```
Rules: network only through the shared `Net` (robots, 1 req/s/host, breaker, conditional GET);
`parse` is **pure** (no network, deterministic, fixture-tested; reruns from blobs for free);
adapters never mint entity ids or decide identity: they emit observations and the matcher
attaches them; never coerce a value the source didn't state (`raw` literal + proposed value);
a parse failure is an `absence` with a reason, not an exception that drops the snapshot.

### 15.6 Publish step (`scripts/build.py`)
1. Load + validate profiles and all `data/` records against the schemas; fail the build on error.
2. Resolve each entity: accepted claims (+ inherited, + derived) → `specs[key]` (headline value,
   `conditional[]`, `alternatives[]` when official≠measured or conflicted). Pure function.
3. Strip private fields (`source.snapshot`, locators into private blobs, candidate/rejected
   claims, `listing` entities beyond alias+link).
4. Emit `manifest.json`, `categories.json`, `<cat>/schema.json`, `<cat>/index.json`
   (compact, sharded over ~2 MB), `<cat>/facets.json`, `<cat>/products/<id>.json`,
   `lookup/identifiers.json`, `redirects.json`, `build.json`. Shapes: a4-contract.md.

### 15.7 Postgres later (§0.11), same shapes
`entities(id, category, kind, brand, name, doc jsonb)`, `identifiers(entity_id, scheme, value,
market, role, ...)` unique on (scheme, value, market) where role=key, `relations`, `claims(id pk,
entity_id, key, doc jsonb, review_state)` append-only, `resolved(entity_id, key, value jsonb,
status, ...)` + per-category typed views for facets, `snapshots(sha256, source, ...)`,
`requests`, `search_misses`. The JSON files import 1:1; the static export stays as a CDN read path.

### 15.8 Decisions, identity and publication (A3-impl r2, 2026-11-22; implements the Astra data-model review P0/P1)
- **Inputs of record** (git): `data/_ids/registry.jsonl` (anchor `category|scheme|issuer|value|market` -> id, append-only; ids
  are looked up, never reminted; new ids minted in sorted anchor order, length-capped), `data/_ids/tombstones.jsonl`,
  `data/decisions/policies.yaml` (versioned auto-accept policies) and `data/decisions/ledger.jsonl` (human decisions:
  accept/reject claim, approve/reject relation, merge, split). `state/specsheet.sqlite` = f(raw/, these files); acceptance
  test `tests/test_replay.py` deletes it, replays (both source orders, `--no-mint`) and compares ids/links/claims/rejections.
- **Identity** (`scripts/identity.py`): scoped keys (scheme, issuer, normalised value, market, level); GTINs check-digit
  validated, package-level aliases only, never merge keys; one GTIN on unrelated entities -> `identity_conflicts`, excluded
  from lookup; an observation whose keys hit two entities is quarantined unless the ledger merges them; every
  create/attach/quarantine/proposal is an `identity_events` row and `attachments` keeps observation->entity links.
  Source-stated hierarchy is approved by `rel/source-stated-hierarchy@1`; suffix inference only proposes.
- **Claims**: the full validated claim document is stored (`claims.doc`, record.schema `claim`), plus normalised value
  (`scripts/normalize.py`, before acceptance), review state and decision id. Stable claim id = hash of source id, ref, locator,
  key, value, unit, conditions, kind, measurement, extractor name (not version, not record-local `s1`).
- **Resolution** (`scripts/resolve.py`): supersession, then condition groups (headline = profile `headline_condition`, else
  `{}`; no headline evidence = unknown + `conditional[]`), official > derived > reported > measured with other kinds as
  `alternatives` (never conflicts). Inheritance over approved parents in topological order, only for specs whose profile
  `level` does not vary below the parent; packages never inherit `phys.*`; inherited sources re-pointed at the ancestor URL.
- **Publication**: trusted `<cat>/…` = accepted claims + approved links only (facets, lookup); `preview/<cat>/…` = deltas
  incl. candidates and proposed links. Details validate against `schemas/public-detail.schema.json` at build time.
- **Deferred**: non-US Lenovo MTMs are retained as `regional_observations` + `coverage` (evidence by reference: snapshot + MTM),
  not yet materialised as claims (needs a streaming/partitioned store); stale `parsed/*.json` cache keys (P1-9); profile-driven
  category metadata/columns (done in 15.9); hash-partitioned shards; typed CTO constraints; Apple
  one-page-many-identifiers split.

### 15.9 A category = profile + category.yaml + source registration (A3-impl r3, 2026-11-23)
- `research/<cat>/spec-profile.yaml` (A1: specs, facets, identity levels) + optional `research/<cat>/category.yaml` (A3: name, columns,
  market_filter, variant_label, importer `features`, brand aliases/names, stem rule; documented in `scripts/catmeta.py`) + `SOURCES` entries in
  `crawler/adapters/registry.py` (each names an `importer`: lenovo-psref | asus | apple | generic | strip | **model**). Nothing else names a category:
  `v1_publish.py` publishes every category present in the store; `import.py` ingests every source whose category has a profile.
  `tests/test_new_category.py` proves it with a throwaway root (`SPECSHEET_ROOT`, `sources.extra.json`).
- `model` importer: one page/row = one model; mfr_model key is brand-scoped and NOT market-scoped, so an exact normalised string from two
  sources is one entity (accepted by identity, no policy needed); stem equality (identity.md rule) only PROPOSES `possible_match`
  (never transmits claims). mtm -> package entity, hw_rev/edid_id -> revision child. Certifier/regulatory rows mint models but never name them.
- Policies 2026-11-23: `claim/mfr-monitor-structured@1`, `claim/energystar-certified-power@1` (per-field key list), `claim/displayhdr-certified-tier@1`.
- Size budget: `docs/api/v1` <= ~80 MB of bytes (Pages limit headroom); v0 `<cat>/products.json` now carries column fields only. Measured 68 MB.
- Size budget (2026-11-23, review 2 risk 5): `data/release-budget.json` - live API warn 100 MiB / fail 150 MiB (logical bytes), main packed warn 250 MiB / migration trigger 500 MiB; `scripts/release_manifest.py` measures logical/gzip bytes, file count, changed bytes vs the previous gh-pages snapshot and packed sizes per release.


### 15.10 Document input pipeline (A3 document pipeline, 2026-11-24)
- `crawler/documents.py` discover (offline, every source's snapshots + crawl.py v0 assets; each link tied to the page it was on) -> fetch (one pass,
  adopt bytes already on disk, else polite GET; `raw/_documents/` append-only log + blobs, snapshot = content hash) -> extract (`pdftotext -layout`
  + `-bbox-layout` column blocks; empty text layer -> tesseract with mean word confidence). `scripts/docattach.py` (transform docattach@1, pinned)
  attaches claims at import: identity guard (linking page's entity + exact identifier in the document text; multi-model docs need a block naming
  the model; else `document_proposal` event), explicit port attribution, provenance conditions {document_kind, ocr?} that `resolve.py` neither
  groups nor bases on; list items are completed from compatible document rows (note `merged:`), disagreements stay conflicts. Document hosts
  (`kind: document_host, inherit: linking_page` in data/source-policy.yaml) take the linking page's disposition. Gaps: `scripts/coverage_audit.py`.
- Review 6 (2026-11-25; docattach@2 / docparse@2 / docspec-attach@2): (1) a claim is bound by its own row scope (block, else page, else the
  document only when it names no other model; uncatalogued siblings count), OCR identity needs confident TOKENS (`raw/_documents/ocr/`
  sidecar, `documents.py ocr-tokens`; a page mean never vouches) and makes the claim OCR-dependent, variant/region/shared-SKU ambiguity keeps
  it a candidate (docparse-review@2); trust is carried as provenance conditions identity / identity_scope / identity_variant. (2) Combination
  context is document scope across blocks and pages; port rows map onto the linking observation's own out.ports claim. (3) Provenance is per
  linking edge (source entry, claim locator.linked_from, documents[] row with linked_from); a document_host inherits only from a listed
  `kind: maker` page that is not itself a document, and documents[] never falls back to the record's first source.
