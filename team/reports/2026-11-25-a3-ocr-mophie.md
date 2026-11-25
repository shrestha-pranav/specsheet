# A3: spec-image OCR + mophie manual binding (2026-11-25)
**Result: the pipeline is built and guarded, but it adds 0 values.** Anker spec images carry no PDO/PPS tables, and mophie product pages do not
link their manuals. `RELEASE_DRY_RUN=1 scripts/release.sh`: rc 0, strict parsers, all tests and smokes pass, local gh-pages d9a98565. Nothing committed or pushed.

## Decide / open questions
- **New pending policy `claim/spec-image-power-pdo@1`.** Extractor `specimg@1`, source `documents`, kind official, tier manufacturer. Keys: pd.pps,
  pd.pps_max_voltage, pd.pps_max_current_a, pd.max_fixed_voltage, out.ports. Pinned to imgattach@1 sha256:5bed2ab2b49ef89d9931. It was locked at
  19:07Z (another agent's import ran after I inserted it; the content has not changed since). Approval fields left empty. `specimg-review@1` is never in a policy.
  It matches 0 claims today, so approving it has no effect until a maker publishes spec cards.
- **mophie is blocked on a binding rule.** None of the 33 product snapshots (23 power banks + 10 chargers) links a PDF. The only manual link
  is the footer "Product guides" link to /pages/user-manuals, a hub page that is not registered. Under the per-edge rule, no manual can bind to a product.
  Option (needs a ruling): register the hub as one snapshot and allow the edge "hub page -> document" only when the PDF text names the entity's own mophie SKU
  (text layer, review-6 scope rules). linked_from would then be the hub URL, not the product page, which changes edge_verified. I built nothing for it.
- **OCR recall gap (low value).** Grayscale + 2x misses white text on light or photo backgrounds. 71/281 images give fewer than 5 words.
  A contact sheet of 12 of them shows headlines and photos, no spec tables. An inverted second pass would cost about 3.5 min CPU. It is not worth it for Anker.
- No unlisted hosts: every image is on cdn.shopify.com (an existing document_host).

## Numbers
- Spec images (file name matches spec/param/label/_TDnn) in the v0 Anker store: **1,617 links**, all already on disk, so **0 HTTP requests**.
  - 1,256 sit on v0 pages whose URL matches no registered v1 snapshot, so no entity observation and no edge.
  - 361 links (281 unique images) are bound to 54 anker-us-chargers/powerbanks pages.
- OCR: 281 images, about 3.5 min with 10 workers (tesseract 5.3.4, CPU only). Cache: raw/_specimages/ocr/<sha>.json (imgocr@1).
- Binding of 281 image-page edges:
  - 40 inherit via a single-SKU page;
  - 211 are on multi-SKU pages with no confident OCR model, so they drop;
  - 30 are vetoed by the file name. Example: a2667's only SKU is A2667114, but its images are named A2667111/A2667113;
  - 0 are bound by an OCR model number.
- Value gate: 16 lines dropped for low confidence (value-token mean < 70), 3 for ambiguity.
- Parser output over all 281 images: **1 row in total**. It is A2687 TD04, "In AI Mode, the PPS range is 5 - 11V/5A", outside any output
  context and conditional on a mode, so nothing is emitted. **Claims: 0. Proposals: 0.** Proposals are only emitted when an unbound image has rows.
- Coverage (scripts/coverage_audit.py, /tmp/a3-before.sqlite -> /tmp/a3-after.sqlite), trusted:
  - power-banks pd.pps 19.6% -> 19.6%; per-port pps 5.4% -> 5.4%;
  - chargers pd.pps 7.8% -> 7.8%; out.ports.pps 4.2% -> 4.2%.
  - The brief's "PB PPS 16.3%" is the preset view. It is also unchanged, since no claim was added.
- **False-positive spot check:** no attached values exist to check.
  - I read the OCR text of all 25 images containing any V/A/W/PPS token. None prints a PDO table.
  - Two are readouts that a weaker parser would misread: the A2345 screen readout "20.0V | 5.0A 100.0W" (a live display value, not a PDO) and the A2687 AI-mode PPS note.
  - Visually checked 15 images: A2667 TD01/TD03, A2345 TD05, A2687 TD04, and a 12-image contact sheet. Recorded text agrees with the images; none carries a spec table.

## Built
- `crawler/specimages.py` (new): `discover` (offline; records the v0 -> registered-page edge, the page's own variant SKUs and the file-name model tokens), `ocr`, `stats`.
- `scripts/imgattach.py` (new, imgattach@1):
  - single-SKU inheritance, or an OCR model at >= 60 per word with no sibling;
  - a file-name SKU veto;
  - a value gate (value-token mean >= 70, ambiguity patterns, a rejected line closes the open row);
  - claims via docattach.claims_for, so grammar and port attribution are unchanged;
  - document_kind spec_image, ocr conditions, one source per image x linking page with linked_from.
- `tests/test_imgattach.py` (new, 10 tests):
  - A2667 spec card corroborates the manual (pps 3.3-16V 3.25A, 16 V, 3.25 A, 20 V);
  - a multi-SKU page with no OCR model does not attach;
  - a multi-SKU page with an OCR model gives review only;
  - a low-confidence model token drops;
  - the file-name veto (real a2667 naming), and another model in the image;
  - mean 66 < 70 drops;
  - "3.3-1 1V" is never attached;
  - ambiguity patterns, and the policy pin.
  - The real A2667 images carry no PDO, so the A2667 card is synthetic.

## Shared-file changes
- `scripts/import.py` (+3/-1): import imgattach, pin `IA.TRANSFORM` in current_fp, call `IA.apply(worlds, events, doc_stats)` after DS.apply.
- `data/decisions/policies.yaml`: +1 pending policy, inserted before claim/document-spec-r2@2. `policy-lock.jsonl`: +1 line (written by import).
- Not touched: documents.py, _docparse.py, docattach.py, source-policy.yaml, A2's adapters. imgattach's fingerprint covers docattach.py and _docparse.py,
  so editing either needs a re-pin.

## Addendum: mophie hub, per the coordinator ruling (11:35)
- **Hub registered:** `data/document-hubs.yaml` (new) lists www.mophie.com/pages/user-manuals as kind hub, brand mophie, for chargers and power-banks.
  - `crawler/dochubs.py` (new) fetched it with 1 GET through crawl.Net (robots, honest UA) into raw/_documents/hubs/. It found 37 PDF links.
  - `documents.py discover` merges them as found_on {source_id: None, link_role: hub}, and decide() treats them as fetchable.
  - `fetch --hub-only` made 37 GETs, all 200. Extract: 37 documents, 107 OCR pages.
  - A hub is never a source: docattach ignores these edges, verified by a test.
- **Binding:** new transform `scripts/hubattach.py` (hubattach@1, extractor hubdoc@1 / hubdoc-review@1). Separate from docattach, so document-power-pdo@4 stays pinned.
  - The PDF text must quote an own SKU or model, using docattach identity plus review-6 scope_of.
  - Shared identifier / variant / region = no bind (a proposal event).
  - Shared rows of a multi-SKU manual bind to nobody.
  - Uncarried SKU = nothing.
  - Locator records {linked_from: hub, link_role: hub, identity_basis: document_quote}. Source and documents[] entries carry linked_from = hub URL.
  - The document's host is www.mophie.com (maker), so the disposition is direct. No new host is needed.
- **Fixtures:** `tests/test_hubattach.py`, 7 tests, all pass. Positive quote bind; multi-SKU shared rows don't bind (only the SKU's own block does); uncarried SKU;
  shared identifier; unregistered hub; docattach ignores hub edges; policy pin.
- **Policy:**
  - `claim/hub-document-power-pdo@2` is pending, pinned to hubattach@1 sha256:ee5821197077e20d3d99, approval fields empty.
  - @1 was locked by my dry run at 19:28Z. A docstring-only edit was then needed: test_source_policy f16 flags any scripts/*.py that both imports yaml and names the source-policy file.
  - So @1 moved to retired_policies verbatim with a `retired` line. check_lock(write=False) shows only @2 as new.
- **Result: 0 claims.**
  - 36/37 manuals print no SKU or model number in their text (it is only in the file name, which is not identity evidence).
  - The one that does (401122024, PS-SLIM-20K quick start) binds, but has no PDO rows.
  - Across all 37 manuals there are no PDO/PPS rows at all: only "up to 30W / 45W" prose and "2.4A" USB-A lines.
- **Fill, trusted, before -> after:** power-banks pd.pps 19.6 -> 19.6%, out.ports.pps 5.4 -> 5.4%, out.ports.fixed_pdos 40.5 -> 40.5%;
  chargers pd.pps 7.8 -> 7.8%, out.ports.pps 4.2 -> 4.2%, fixed_pdos 27.5 -> 27.5%, pd.max_fixed_voltage 28.2 -> 28.2%.
  Source: /tmp/a3-before.sqlite vs scratch /tmp/a3-after2.sqlite.
- **A2687 AI-mode PPS line:** a carve-out would be worth +1 charger at most. A2687 has no pd.pps claim today; adding it moves chargers pd.pps 7.8 -> about 8.5%.
  - If done, only pd.pps true, from a "the PPS range is" note on a single-SKU page. Never the range: it is conditional on AI Mode, and the 5 A ceiling is not the device's normal profile.
  - Its digits' confidence is 69.6, just under the 70 gate, so it would also need a gate exception.
  - Recommendation: not worth a rule. Have A2 read A2687's manual instead.
- **Release dry run: BLOCKED, not by my changes.** `--strict-parsers` fails on PARSER DRIFT in claim/mfr-ssd-sandisk-datasheet@1. sandisk_datasheets@1 changed, an in-progress edit by another agent.
  - The full test loop also fails test_match (A2687/WD matcher precision) and test_source_policy f1 ("teal" fixture). Neither touches my files.
  - All my tests pass: test_imgattach, test_hubattach, test_documents. Scratch import without strict: rc 0.
- **More shared-file changes:**
  - `scripts/import.py`: +HA import, pin, `HA.apply` line.
  - `crawler/documents.py`: hub-link merge in discover, decide() accepts hub edges, `fetch --hub-only`.
  - `policies.yaml`: +@2, @1 retired. `policy-lock.jsonl`: +1 line, written by import.
  - New files: data/document-hubs.yaml, crawler/dochubs.py, scripts/hubattach.py, tests/test_hubattach.py.
