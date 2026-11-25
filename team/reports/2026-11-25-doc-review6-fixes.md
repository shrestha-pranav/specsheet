# A3-impl: review 6 document-pipeline fixes (2026-11-25)
**`RELEASE_DRY_RUN=1 scripts/release.sh "doc review-6 fixes"`: rc 0.** Strict parsers, all tests and smokes pass, local gh-pages ff93dc1b. Nothing committed or pushed.
- **Decide (pending, locked by the dry run):** `claim/document-power-pdo@4` (docparse@2, docattach@2) and `claim/document-spec-r2@2` (docspec@1, docspec-attach@2). @3 and r2@1 moved to retired verbatim (hash checked before the dry run) with `retired` lines. Approval fields left empty.

## Published values that change (replay of all 43 power + 150 spec documents; every other record identical)
- **Trusted, anker-a2669:** `pd.pps` true is withdrawn (it came only from the manual). `out.ports` and `pd.max_fixed_voltage` keep their page values but lose the manual as a source. Why: the manual file is `A2669211_22`, another SKU of the A2669 base, and our US SKU A2669113 is named nowhere. Its 3 claims are now `docparse-review@2` candidates (in preview).
- **Preview, anker-a2147:** 4 OCR candidates withdrawn (pd.max_fixed_voltage 20, pd.pps, pd.pps_max_voltage 16, pd.pps_max_current_a, was conflicted), and the manual leaves documents[]. Why: the only identity token, "A2147_", has OCR confidence 0.0 on a page whose mean is 84.3. Now an `identity_low_confidence` proposal.
- **documents[]:** 399 records gain `linked_from`; nothing else added or removed. Docspec: the same 145 claims, 0 value changes.
- **Fixes 2 and 3 change no published value today.** The 14 attachments have 1 edge each and 0 edges fail verification. Fix 2 only moved device rows to multi in 3 unattached documents (A110R, A1340, Shargeek 170).

## What changed
1. **Identity binding** (`scripts/docattach.py`):
   - A row is scoped by its own block, then its page, then the document (only if it names no other model). Siblings include uncatalogued models (same identifier shape, or a token after "Model:") and catalogued entities outside the lineage, substring-related included. Identifiers of 3 chars or fewer need a model label ("USB-C3" is not C3).
   - Variant ambiguity (another SKU of the same base, a foreign region token in the file name, an identifier shared with another entity) keeps a claim a candidate (`docparse-review@2`).
   - OCR identity needs every word of the mention at token confidence 60 or more, and makes the claim OCR-dependent (`docparse-ocr@2`) even with text-layer rows. OCR rows are judged by their lowest digit-word confidence; no token data drops the row.
   - Conditions carry `identity` / `identity_scope` / `identity_variant` (added to resolve.py PROVENANCE). New sidecar `raw/_documents/ocr/<sha>.json` from `documents.py ocr-tokens`: 62 pages, all reproduce the stored text.
2. **Combo context** (`_docparse.py` v2): mode and "+" context last across blocks and pages until an explicit mode heading (fail closed). Ports map onto the linking observation's own official out.ports claim. When layouts disagree, only explicit single-port rows are attributed.
3. **Policy edge:**
   - One source entry, one claim (`locator.linked_from`) and one documents[] row per verified edge (URL x snapshot x page x linking page). An edge is verified only when its page URL equals the URL of the entity's own observation.
   - `documents()` has no fallback. Inheritance needs a listed `kind: maker` page on a different host that is not itself a document URL.
   - Adapter documents get their own page as `linked_from` (this kept the 248 CyberPower/Salsify document links).

## Fixtures (`tests/test_documents.py`, 33 tests)
- **Fix 1:** unknown sibling, two models in one block, base-model/regional variants, shared SKU, low- vs high-confidence OCR identity with text-layer PDOs, high page mean with uncertain digits, short identifiers.
- **Fix 2:** split-block "+" heading, page-spanning table, conflicting layouts bound to the linking observation, valid sectionless row, order-independent conflicts.
- **Fix 3**, through `apply()` and then the gate: allowed + withheld pages in both orders; identical bytes at two URLs; an unverified edge; Salsify/CDN-to-CDN/document-URL/unlisted/missing edges; documents() with no fallback.
- **Pins:** power-pdo@4 and spec-r2@2 fingerprints, plus the retired entries.

## Shared-file changes
- `scripts/import.py` (documents table gets `linked_from`, one row per edge; adapter documents get their page edge), `scripts/v1_publish.py` (documents carry `linked_from`, no page_url fallback).
- `scripts/source_policy.py`, `scripts/resolve.py` (1 line), `crawler/documents.py`, `data/decisions/policies.yaml` + 2 lock lines, `ARCHITECTURE.md` §15.10.

## Open
- Prose "Charging and Recharging Simultaneously" matches the multi heading and suppresses A110R's table. Fail closed, nothing lost today, may need a heading-only rule.
- A2669 needs a reviewed statement that A2669211 and A2669113 are electrically identical before it can attach.
