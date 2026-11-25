# A3-impl + A2: generic document input pipeline (2026-11-24)

## Decisions and open questions
- **Approve (pending, locked by the dry run):** `claim/document-power-pdo@1`. Source `documents`, extractor `docparse@1` (text layer only), keys pd.pps, pd.pps_max_voltage, pd.pps_max_current_a, pd.max_fixed_voltage, pd.epr, out.ports. Fingerprint pinned. OCR claims (`docparse-ocr@1`) stay candidates.
- **Source policy 2026-11-24.6:** new kind `document_host` (`inherit: linking_page`) for cdn.shopify.com, cdn.shopifycdn.net and 3 CloudFront hosts. A document there gets the disposition of the page that linked it; with no linking page it is withheld; inheritance never chains. s3.belkin.com added as a Belkin maker host.
- **Scope cut by coordinator:** charger and power-bank parsers only; the rest is under "Next".
- **Open:** the Anker A2697 page now carries B2697 identifiers but its manual says A2697, so the manual is a proposal, not attached. Attach it via a reviewed crosswalk ledger line?

## Acceptance: anker-a2667
- Trusted `out.ports` is known, note `merged: page rows completed from linked documents`.
- USB-C 1 and USB-C 2: pps `3.3-16V 3.25A`, fixed `5V3A 9V3A 15V3A 20V3.25A`, max_w 65 (page value, unchanged). USB-A: pps stays null (the manual prints none for it).
- Read only from the manual's "Use One Port" section; the combination sections ("Use Two Ports", "USB-C1 + USB-A") never set a port.
- Device level: pd.pps true, pd.pps_max_voltage 16, pd.pps_max_current_a 3.25, pd.max_fixed_voltage 20.
- Source s1 = `…A2667_US__Manual…pdf#page=2` ("manual (PDF p.2)", `linked_from` the a2667 page). The manual is also listed in `documents`.

## Counts
- **Found:** ~18.3k raw PDF links (12.7k v0 assets/extract, 5.6k v1 snapshots) -> **1,921 unique**; Belkin's 8.8k were mostly one warranty PDF (skipped). Decisions: 1,354 fetch, 322 dedicated adapter (Kingston, SanDisk datasheets, CyberPower), 150 marketing, 36 other, 59 page not registered.
- **Fetched:** 199 snapshots in `raw/_documents/`: 181 adopted from bytes already on disk (no request), 21 GETs for chargers/power banks (18 ok, 1 404, 1 robots, 1 not a PDF). **1,308 deferred by category**; next round core first (TVs, SSDs, routers, laptops, monitors).
- **Parsed:** 43 charger/power-bank documents, 62 pages OCR'd (mean confidence kept as a claim condition; pages under 60 dropped). 18 entity attachments (2 are link-only, no claims).
- **Proposals:** 52. 49 model not named (mostly one INIU B43 manual linked from 42 pages); 3 multi-model documents with no row for the model.
- **New claims:** 38 on 11 entities, 0 conflicts after resolution. Shown as accepted+candidate; all 6 candidates are OCR.
  - chargers: pd.max_fixed_voltage 7+1, out.ports 6, pd.pps 4+1, pd.pps_max_voltage 3+1, pd.pps_max_current_a 3+1, pd.epr 1.
  - power-banks: pd.max_fixed_voltage 1+1, pd.pps 0+1, out.ports 0+1.

## Fill rate, trusted, before -> after (`scripts/coverage_audit.py --before`; full table + evidence counts in `team/queue/coverage-audit.md`)
- chargers: pd.pps 7.0 -> 8.5%; per-port PPS (out.ports.pps) 2.1 -> 4.2%; out.ports fixed PDOs 25.4 -> 27.5%; pd.pps_max_voltage 2.1 -> 4.2%; pd.max_fixed_voltage 25.4 -> 28.2%.
- Unchanged: power-banks pd.pps 19.1% / per-port PPS 5.4%; monitors flk.pwm 22.9% / usb.usbc_pd_w 8.1%; ssds hw.dram_type 52.4% (no document parser yet for monitors/SSDs).

## Built
- New: `crawler/documents.py` (discover/fetch/extract), `crawler/adapters/_docparse.py` (PDO/PPS grammar reusing `_powerbank`/`_charger`), `scripts/docattach.py` (docattach@1: identity guard, port attribution), `scripts/coverage_audit.py`.
- `tests/test_documents.py` (17 tests): A2667, multi-model, OCR, non-English duplicate, model mismatch, ambiguous port, input section, mains range, document-host policy, merged gate. Fixture `tests/fixtures/documents/a2667-manual.json`.
- Rules: a document port row maps onto the page's rows only by exact port-token cover; unnamed PDO lines are device-level only; two different rows for one port in one document drop that port. `document_kind`/`ocr` are provenance conditions: agreement is one value, disagreement a visible conflict.

## Shared-file changes (all small)
- `scripts/import.py` (+9/-4): DA import + fingerprint pin, `DA.apply` after XW.apply, new table `source_links(entity_id, sid, linked_from)`, `documents` stats.
- `scripts/resolve.py`: PROVENANCE stripped from grouping/basis; `_item_merge` (one page assertion + row-compatible document assertions, page fields never overridden); `supports()`.
- `scripts/v1_publish.py`: reads source_links, url refs `{url, linked_from}`, support via `R.supports`, sources carry `linked_from`. `scripts/source_policy.py`: `document_host` validation, `disposition(url, linked_from)`, merged values need every source allowed, `page_url()`.
- Also: `data/source-policy.yaml` (.6), `data/decisions/policies.yaml` (+1 pending), `ARCHITECTURE.md` §15.10. Nothing committed or pushed; no stash/checkout/reset/restore.

## Verification
`RELEASE_DRY_RUN=1 scripts/release.sh "document pipeline"`: rc=0, strict parsers, all tests and both smokes pass, local gh-pages orphan 7d79d9b1. The first dry run failed on my own test's missing `decision` field; fixed.

## Next
1. Fetch the 1,308 deferred documents and add parsers: SSD DRAM/NAND/controller (+ `if.protocol=usb` from SanDisk portable datasheets, coordinator FYI, deferred), monitor PWM/USB-C PD, TV 4K120, router radios, laptop RAM/ports.
2. OCR of label images (the audit counts gallery images named spec/label per v0 store).
3. Bind the 232 unbound v0 links (Satechi/INIU/EcoFlow pages whose URLs differ from the v1 snapshots).
4. Page-parser duplicate rows (A2669 has both "USB-C 1 / C 2" and "USB-C1/C2") block attribution.
