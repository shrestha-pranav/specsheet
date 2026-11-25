# Astra review 6 — document pipeline
Static review of the requested inputs only; no code changes or tests executed. Ranked fixes:

1. **P1 — Bind every claim to a model/variant/region and carry identity evidence trust.**
   `scripts/docattach.py:229` accepts any model/SKU mention anywhere; `scripts/docattach.py:236` detects other models only among existing same-brand/kind entities and excludes substring-related identifiers.
   A family manual naming an uncatalogued sibling therefore bypasses row scoping; even detected families pass a block mentioning both models (`scripts/docattach.py:241`). Model-level matches do not establish variant or region compatibility.
   OCR identity text is concatenated without confidence filtering (`scripts/docattach.py:80`, `crawler/adapters/_docparse.py:177`): a low-confidence OCR model mention can authorize text-layer rows whose claims carry no OCR flag (`scripts/docattach.py:130`).
   Page-average confidence (`crawler/documents.py:445`, `crawler/documents.py:459`) also masks uncertain model tokens and electrical digits; the threshold at `scripts/docattach.py:142` filters claim rows, not identity evidence.
   **Fix:** require unambiguous model-scoped evidence plus applicable variant/market constraints; preserve token/row confidence and propagate OCR dependence from identity through claims, retaining candidate status until reviewed.
   **Exit:** fixtures for an unknown sibling, two models in one block, base-model/shared-SKU regional variants, and low-confidence OCR identity with text-layer PDOs produce proposals/candidates, never trusted cross-attachments. A high page mean must not rescue uncertain critical digits.

2. **P1 — Preserve combination context across layout boundaries before merging port facts.**
   `crawler/adapters/_docparse.py:73` resets `combo` every block; `crawler/adapters/_docparse.py:101` sets only that local flag for a `USB-C1 + USB-C2` heading. A following block containing `USB-C1: 5V 3A` is treated as unstated/single-capability evidence (`crawler/adapters/_docparse.py:110`).
   `mode` also resets every page (`crawler/adapters/_docparse.py:70`), so continued multi-port tables can leak into per-port facts and device maxima (`scripts/docattach.py:145`).
   Attribution then uses the last non-document out.ports claim, without checking its linking observation or official kind (`scripts/docattach.py:92`), allowing another page's port layout to supply names/types.
   **Fix:** maintain explicit section/table scope across blocks/pages, fail closed on ambiguous continuations, and bind the port map to the actual linking observation.
   **Exit:** split-block plus headings, page-spanning multi-port tables, and conflicting port layouts across observations emit no per-port capability claims without explicit single-port scope; valid single-port fixtures remain attributable.
   **Merge assessment:** tests assert compatible completion, unchanged max_w, and visible numeric/scalar conflicts (`tests/test_documents.py:68`, `tests/test_documents.py:85`); resolver implementation is outside scope, so no independent no-overwrite guarantee is established. Incorrectly attributed rows can silently fill page nulls without triggering those conflict checks. Add end-to-end fixtures for these cases and order-independent conflict preservation.

3. **P1 — Preserve the exact document-to-page policy edge instead of first-source inheritance.**
   `scripts/docattach.py:225` deduplicates by document URL per entity, discarding subsequent linking contexts; `scripts/docattach.py:255` keys source entries only by content hash/page and retains the first URL/linking page. Identical bytes from differently governed URLs can collapse provenance.
   Document-list entries omit linked_from (`scripts/docattach.py:249`), causing `scripts/source_policy.py:315` to fall back to the first eligible record source (`scripts/source_policy.py:317`), potentially a different maker disposition.
   Recognized document-host chains stop at `scripts/source_policy.py:188`, but the shared Salsify CDN is classified as maker/free (`data/source-policy.yaml:143`), so it receives unconditional free disposition and can act as an inheritance endpoint. The no-chain guarantee is classification-dependent.
   **Fix:** key provenance by document URL, snapshot/page, and verified linking observation; retain linked_from on document entries; classify shared CDNs consistently and require an eligible maker-page edge.
   **Exit:** one entity with allowed and withheld linking pages, identical PDF bytes at different URLs, and Salsify/CDN-to-CDN cases preserve their respective dispositions regardless of discovery/source order; missing or ambiguous edges remain withheld. Exercise actual attachment-to-policy flow, beyond the direct policy calls at `tests/test_documents.py:230`.
