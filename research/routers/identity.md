# Wi-Fi routers & mesh: identity rules (A2, 2026-11-23)

Levels follow spec-profile.yaml: family > model > revision > configuration > package. Adapters only emit observations; the importer decides entities.

## What each level is, per brand (measured on the three built adapters)
| level | TP-Link (tplink-us-routers) | NETGEAR (netgear-us-routers) | ASUS (asus-us-routers) |
|---|---|---|---|
| family (`series`) | URL stem before the digits (archer-ax, deco-be, deco-x) | slug letters (rax, rbe, rbk) | URL group (asus-wifi-routers, asus-gaming-routers, asus-zenwifi) |
| model (`mfr_model`) | page model name: Archer AX55, Deco BE25 | slug upper: RAX54S, RBE972SB (kit code = pack size) | title head: RT-AX86U Pro; ZenWiFi XT8 = the parenthesised code |
| revision | hardware version V1 / V4 / V4.60 (support page selector) | not published | not published (revisions are sold under new names: RT-AX86U vs Pro) |
| configuration (`mfr_sku`) | not published (retail pack suffix lives on retailers) | JSON-LD sku RAX54S-2AZNAS (alias-level `gtin` too) | not published; ZenWiFi pack codes (XT8 (W-3-PK)) kept as aliases |
| package | pack (1/2/3-pack) in the Deco page, not separately coded | RBE972 / RBE973 differ by pack: model-level | same as TP-Link |
Key facts:
- **Revision is the problem level.** TP-Link sells one model name under V1/V2/V4/V4.60 with different SoC vendor, RAM, flash and sometimes
  radios (Archer C7: Atheros v1-v3, QCA v4, MediaTek v5). The support page lists the versions (72 of 106 TP models have a list; 35 have 2, 14 have 4,
  one has 13) but the spec page is served for ONE default version, and /v1/ /v4.60/ URLs return identical HTML. Do not attach per-version specs
  to the model: spec claims from the TP-Link page belong to "the default version at fetch time" and the hardware version list is a model-level claim.
  Since A3-impl (2026-11-23) tplink_routers emits one revision entity per listed version (scheme `hw_version`, value `<model> <version>`, extra `revision_label`); the spec-table's revision-level
  specs go to the default version only. Published in the model detail `revisions[]` (team/briefs/a4-contract.md), not as index rows.
- **FCC ID is an alias scheme, never an identity key.** Format = grantee code (3 or 5 chars) + product code (2AXJ4 + AX55, TE7 + A8). Reasons: one product
  code spans hardware versions and regional SKUs (V1/V4 may share one grant or have two); Wi-Fi 6E/7 variants and the same board in a kit and a single
  router can carry several IDs; a single model may have Class II permissive changes under the same ID. Use it to JOIN evidence (internal photos, test
  reports, chipset), and as a revision hint when two filings exist for one model name. Scheme `fcc_id` is declared `alias_only`.
- **Marketing class is an alias only** (AX5400, BE19000): sums of band rates, reused across unrelated models (AX3000 appears on Archer AX55, AX3000 non-Pro,
  Archer AX53...). Retail titles carry it; never merge on it.
- **Kits are models, not variants, for NETGEAR/ASUS ZenWiFi; for TP-Link Deco the pack count is a configuration axis of one model.** A Deco BE25 page
  covers 1-, 2- and 3-pack with the same specs per node; the specs are per node, `gen.pack_count` is the variant axis.
- **Region**: TP-Link US (`/us/`) vs EU firmware lists differ; NETGEAR SKU suffix (-2AZNAS vs -100NAS) encodes region/packaging; keep `market` on identifiers,
  strip nothing (profile category.yaml `strip_market_suffix: false`).
- **Retail listings (Amazon/Best Buy titles, "Archer AX55 AX3000 Dual Band Gigabit Wi-Fi 6 Router") are aliases.** Several retailer titles even name the wrong hardware version.
- Suffix quirks seen: TP-Link `-pro`, `-outdoor`, `-poe`, `-5g` are different products (not variants); `v2` in a URL slug (archer-c3150-v2) is a separate marketing page for a version.
