# A2-mon r5 (2026-11-25): monitors flicker/KVM/native refresh, stations chemistry + UPS prose, Dell scout
**Presets (docs/api/v1, bare import --strict-parsers + build under flock):** no-pwm-usbc-monitor flk.pwm 350/442 79.19% -> 352/442 79.64%, **still fails (needs 354)**.
**station-lfp-1kwh 78.72% fail -> 81.25% PASS** (chem 39/48, cap.energy_wh 59/71). monitor-1440p-144 (res.refresh_native) 25.4% -> 41.5%. Nothing committed; release.sh not run.
## Decisions / open questions first
- **Coordinator: 4 pending policies to review.** claim/mfr-monitor-structured@9 (lg_us@4, asus_monitors@4; widens lg-us usb.kvm + res.refresh_native,
  asus res.refresh_native), claim/mfr-monitor-benq@4 (widens usb.kvm), claim/mfr-power-stations-structured@6, rel/bundle-contents@6 (pin only).
  @8/@3/@4/@4 retired verbatim. stations@5 + bundle@5 were issued and locked by this round's first import, then superseded the same round by @6
  (capacity-label fix found after that import); both sit in retired_policies, never approved.
- **Flicker gate can't reach 80% from stored LG/BenQ pages.** All 10 BenQ gap pages and 11 of 13 LG gap pages contain no flicker statement
  anywhere (not in text, alt text or CMS JSON). Lenovo PSREF and the datasheets are already used up (A2 independent sources). The remaining 2 rows need a new source: Dell is not
  in this gap set. Options: re-fetch the LG gap pages (content may have changed since 11-23) or accept 79.6%.
- **LG badge rule (A1 please confirm):** flk.pwm none from alt text 'Flicker-Free / Discomfort Glare Free / Low Blue Light Platinum'. The alt text does not
  print "UL". I took the line 'Flicker-Free' as the badge name, and the asset's own SKU metaproperty must equal the page model exactly. Revert if you want UL/TÜV printed.
- **UPS ruling, as implemented:** the schema has no `max` qualifier, so '<', '≤', 'sub-', 'under', 'within' publish as value 'up to N'
  (normalize -> qualifier up_to). Pre-existing labelled rows like Jackery 'Backup UPS: ＜20ms' still publish a bare 20 with no qualifier. I left that alone because it would change approved claims. Fix next round?
- '0ms UPS switching' (Jackery 5000 Plus) is covered by the ruling, but that page already has a labelled row, so prose is not used there.
## 1-3 Monitors (stored pages only, no fetches)
- lg_us@4: +2 flk.pwm (34GX900A-B, 45GX900A-B, both gap rows); +16 usb.kvm True from the spec row 'KVM: Yes'. +401 res.refresh_native, only from a row that is
  one plain 'NHz' ('O/C', 'up to', multiple figures, H/V frequency and Dual Mode pages give nothing). Diff over 504 pages: 0 removed or changed.
- benq_monitors@4: +39 usb.kvm True from 'Professional > KVM Switch: Yes' (136 pages, 0 other changes).
- asus_monitors@4: +4 res.refresh_native, only where the page's own copy says 'native N Hz' (MB16AHG 144, PG27AQDP 480, VG27AQML1A 240,
  VG328QA1A 165). 'Refresh Rate (Max)' never maps. 0 other changes over 346 pages.
## 4-5 Stations
- _powerstation.chemistry() now reads 'LiFePO₄' (subscript 4; the regex missed it): +1 BLUETTI PR100V2 and +4 Goal Zero (36900/37000/37100/37500) bat.chemistry lfp.
  A 'Battery Pack Capacity' label is now a capacity row: +4 Goal Zero cap.energy_wh (+pack V/Ah). Without it, those LFP rows entered the cap gate as unknowns.
- UPS prose (ups_prose/emit_ups_prose) applies only when no labelled row already gives the value, the page resolved to exactly one model, and it is not a package. Comparison tables (text inside <table>) are dropped, and a sentence naming
  another model is skipped. +12 ups.switchover_ms: BLUETTI EL10 x2 pages 10, EL30V2 x6 'up to 10', EL100V2 10; Jackery Explorer 2000 v2 x2 'up to 20';
  Anker A1765 10. EcoFlow '10ms Auto-Switch' / '<30ms EPS' and Jackery 'Power Transition' give nothing. Not used: Jackery HomePower pages (no spec block, so the page can't be tied to one model),
  Anker S2000 (no model stem), Anker C1000 Gen 2 chemistry (only in a comparison table with C1000 and "Other Brand").
## 6 Dell monitors: crawlable, adapter not built (time)
- robots allows /en-us/shop/monitors/apd/; www.dell.com is already in source-policy (maker, monitors). The /apd/ page now server-renders the full Tech Specs
  block (div.spec__item__title + value). The listing page /computer-monitors/ar/all-monitors links the models. Details are in research/monitors/merchants.md. No new domain needed.
## Files
Adapters: lg_us.py v4, benq_monitors.py v4, asus_monitors.py v4, _powerstation.py, shopify_powerstations.py v5, ankersolix_stations.py v5.
data/decisions/policies.yaml (+4 pending, 6 retired); policy-lock.jsonl lines written by import. New tests/test_a2_mon_r5.py (5 cases).
Shared test edits: test_r6.py, test_r7.py (now point at the live station/bundle policy ids). research/monitors/merchants.md (Dell scout).
Not touched: source-policy.yaml, registry.py, import.py, documents.py, _docspec_*, crawl.py.
