# A3-docs-2: doc parsers r3 (TV, router, laptop), 2026-11-25
**Dry run:** `RELEASE_DRY_RUN=1 scripts/release.sh` rc 1 at 11:20. The cause is not this work: `PARSER DRIFT claim/mfr-ssd-sandisk-datasheet@1`, from the in-flight `crawler/adapters/sandisk_ssd.py` edit (A2-ssd). The tests passed before the import step. A scratch import (`--db /tmp --no-mint`, under flock) ran rc 0 with 0 drift. Two retries also failed on other agents' in-flight work: at 11:34 `test_hubattach` pin mismatch, and at 11:38 `test_match` held-out precision 0.875 (Anker A2687, WD SN7100: charger and SSD rows from docs/api/v1, not tvs). My tests pass (test_docspec_r3, test_docspec, test_documents) and r3@1's pin matches the code.
- **Decide (pending, now locked):** `claim/document-spec-r3@1`.
  - Extractors docspec-tv@1 / docspec-router@1 / docspec-laptop@1; transform docspec-attach-r3@1 pinned at `sha256:861d49c06bfd094f72c2`; 17-key allowlist, source_ids [documents]; approval empty.
- **Decide (hook placement, differs from the brief):** the hook is in `scripts/import.py`, not `docspec_attach.py`.
  - Approved r2@2 pins docspec-attach@2, whose fingerprint hashes `docspec_attach.py` itself: any edit drifts it under `--strict-parsers`, and a pending r2@3 would hold back today's accepted SSD/monitor claims.
  - So new transform `scripts/docspec_r3.py` reuses DS/DA helpers unchanged; import.py +3 lines (import, fingerprint, `DS3.apply` after `DS.apply`).
- **No hook needed** in documents.py or _docparse.py.

## Documents
- **Fetched:** 185 GETs at 1 req/s per host, honest UA, robots respected: 184 ok, 1 404 (www.netgear.com RBK13_tcm148-81218.pdf).
  - Only source-policy-listed hosts with crawl agent (www.lg.com, www.vizio.com, cdn.shopify.com); /tmp wrapper filtering `documents.load_discovery`, documents.py unedited.
- **Extracted:** 180 documents for tvs/routers/laptops, including 113 OCR pages, but parsers read the text layer only. 184 TV documents parsed.
- **Not fetched, hosts unlisted in data/source-policy.yaml** (A2-ssd owns that file; needs a maker entry first):
  - tvs: images.samsung.com (145).
  - routers: www.downloads.netgear.com (119), downloads1.netgear.com (1), dl.ui.com (9), www.ui.com (1), static.gl-inet.com (3).
  - laptops: www.apple.com/apple.com (21), download.microsoft.com (3), i.dell.com (2), www.delltechnologies.com (1), www.principledtechnologies.com (2).
- **So routers and laptops have 0 documents on hand.** Their parsers are built and fixture-tested and ready for when those hosts are listed.

## Claims (scratch replay, all under r3@1; 105 total, 87 corroborate, 18 new, 0 conflicts)
- **tvs, 66 entities attached:** hdmi.count 65 (55 agree, 10 new, old LG sheets); hdmi.earc 11 agree; hdmi.has_4k120 + ports_4k120 3 each agree (TCL X11L); refresh.native_hz 11 agree (TCL 144, LG "TruMotion 120 (Refresh Rate 60Hz)"); panel.backlight 3 agree; panel.lcd_type 9 (1 agree, 8 new ips from LG "IPS Panel •" / "Panel Type IPS").
- **Proposals:** 37 multi_model_other_page (a series sheet naming a same-brand model whose page does not link it). These fail closed.
- **Why so few 4K120 claims:** the LG sheets on hand are 2013-2017 models (HDMI 2.0 era). TCL QM7K/X11K print "4 HDMI (One with eARC)" without HDMI 2.1, so nothing is read from them (affirmative only).

## Rules (affirmative only, review-6 identity)
- **Identity:** a verified linking edge, plus an own mfr_model/SKU quoted in the text (or a 6+ char base SKU, marked `identity_variant: model_only`).
  - Never when an unlinked same-brand catalogued model is named. The quoted identifiers go in `locator.identifiers`.
- **Cells:** adjacent (label, value) segments of a `pdftotext -layout` line (handles LG three-column layout); a value repeated in the next column, a size-qualified cell ('98": TBD'), or a key with two values in one document is never read.
- **hdmi.has_4k120:** HDMI 2.1 and a 4K@≥120 Hz figure in the same cell. "HDMI 2.1" alone sets nothing.
- **hdmi.ports_4k120:** only from "<N>x HDMI 2.1 (4K@…)" with no other HDMI version in the cell.
- **panel.lcd_type:** never from brand panel names (HVA/WHVA).
- **Laptop mem.soldered:** needs a slot statement (the ASUS trap). There is no zero or false from silence anywhere.

## D8 preset fill deltas
- **No change** to tv-4-hdmi-4k120, router-wifi7-6ghz, ram-upgradable: every 4K120/refresh claim corroborates, no router/laptop docs fetchable. The 18 new values (hdmi.count, lcd_type) are outside presets and stay preview candidates until r3@1 is approved.

## Files (all mine unless noted)
- **New:** `crawler/adapters/_docspec_{tv,router,laptop}.py`, `scripts/docspec_r3.py`, `tests/test_docspec_r3.py` (5 tests: per category corroborate / new fill / wrong-model doc linked from its own page does not attach; unlinked same-brand model blocks).
- **Shared edits:** `scripts/import.py` +3 lines; `data/decisions/policies.yaml` +1 pending policy before `relation_policies:` (lock line written by the release import).
- **Data:** raw/_documents snapshots, blobs, text and ocr sidecars (append-only), and `raw/_documents/parsed-spec/*.r3.tvs.json`.

## Open
- **Hosts to list:** list the router and laptop hosts above (A2-ssd or the coordinator), then run `fetch` + `extract`. The parsers attach with no code change.
- **coverage_audit.py** still counts only docattach categories (gap carried over from r2). It reports tvs as "fetched, no parser".
