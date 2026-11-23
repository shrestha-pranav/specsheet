# specsheet UI v1 — critique and audit

⚠️ DEGRADED: single-context (delegated read-only run)

Reviewed 2026-11-22 against commit `c91af96`. Reviewer: **astra_reviewer — GPT-6-Astra (`gpt-6-astra`)**. Implementer: **sol_implementer — GPT-6-Sol (`gpt-6-sol`)**. This report records the independent reviewer's findings, persisted by the coordinator because the reviewer role is read-only.

This is the initial review baseline, before fixes. Evidence comes from current HTML/CSS/JavaScript, generated records, the UI brief, PRODUCT.md, DESIGN.md, README and accepted architecture decisions. Rendered appearance and interactive browser behavior remain unverified.

## Verdict

The interface expresses an appropriate reference-catalogue identity. Semantic tables, restrained typography, explicit uncertainty and field-versus-record evidence support the product. The largest gap is task completion: users must decode port data and find the comparison action below 150 results. Preserve the visual system and repair those interactions.

**Ranked findings: 0 P0, 2 P1, 3 P2, 0 P3.** Locations below refer to the reviewed baseline.

## Ranked findings

### 1. P1 — Port details lose structure and units

**Location:** `docs/app.js:55–72`, `scripts/build.py:30–31`. Information design / implementation integrity.

`formatRaw()` converts object arrays into continuous text. Anker A2667 presents repeated `name: C1 · type: USB-C · max w: 65` fragments. Users must reconstruct rows and columns; `max w` exposes a storage key instead of a labelled quantity. Power sharing is similarly compressed into `C1+C2: 45+20; C1+A: 40+22.5; …`.

**Fix:** Add schema-directed display metadata. Render a semantic per-port table with Port, Connector, and Maximum output (W). Present sharing conditions as individually readable entries, retaining their exact recorded statements. Preserve whole-field evidence, unknown/conflicted states and literal ambiguous text; do not infer electrical meanings.

**Acceptance:** A2667 has three distinct port rows and separately readable sharing conditions in product and comparison views, including narrow layouts. Other schemas continue working. Suggested command: `$impeccable clarify`.

### 2. P1 — Comparison action is buried after the catalogue

**Location:** `docs/app.js:206`, `renderTable()`, `renderShelf()`, `.compare-shelf` in CSS. Interaction / responsive design.

The selection shelf follows the entire unpaginated 150-product charger table in normal flow. Selecting two products near the top leaves the primary Compare products action far below the task position. Row highlights confirm selection without offering a nearby next step.

**Fix:** Put selection summary and comparison action before the table, or use an accessible compact sticky region that does not obscure content. Retain names, removal controls and the 2–4 limit; announce selection count without moving focus.

**Acceptance:** Selecting the first two products exposes comparison without traversing 150 rows. Verify 390px width and enlarged text. Suggested command: `$impeccable layout`.

### 3. P2 — Return links discard working context

**Location:** `docs/app.js:294,316,340`, bare `categoryUrl()` calls. User control / implementation integrity.

Product breadcrumbs and Back to products reconstruct a default category URL, dropping search, filters, columns, sort and selections. Removing down to one comparison product restores only that ID. Browser Back is a workaround.

**Fix:** Carry originating category state through product/comparison navigation and explicit return links. Preserve remaining selections after removal. Direct shared product URLs may fall back to defaults.

**Acceptance:** Configure a listing, inspect and compare products, then use visible return links; the working view is restored. Suggested command: `$impeccable harden`.

### 4. P2 — Compact controls miss the project touch-size target

**Location:** CSS `.theme-control select`, `th button`, `.column-options label`, `.compare-shelf .selected-items button`, `.compare-table .remove`. Accessibility / responsive design.

Theme control is 34px high, column labels 33px, selected-item removal 32px, comparison removal 28px; sort buttons remove minimum height. These require precise tapping relative to the design's 44px target. Dimensions alone do not prove a WCAG 2.5.8 violation: rendered spacing and exceptions were not measured.

**Fix:** Increase effective hit areas, especially on coarse-pointer layouts, retaining compact table text. Check spacing/focus in a browser. Suggested command: `$impeccable adapt`.

### 5. P2 — Column chooser is a flat 24-field list

**Location:** `docs/app.js:206`, `.column-options`. Information architecture / efficiency.

The charger chooser puts all 24 fields in an ungrouped scrolling checklist, although the schema already supplies meaningful groups.

**Fix:** Group by schema group and offer a default-column reset; retain selection and keyboard access. Suggested command: `$impeccable distill`.

## Provisional design health

Source-based judgments, not rendered usability results.

| Heuristic | /4 | Evidence |
| --- | ---: | --- |
| Visibility of status | 3 | Loading/counts; distant selection action |
| Match with real world | 2 | Storage keys and compressed conditions |
| User control | 2 | Return links lose context |
| Consistency | 3 | Familiar tables and disclosures |
| Error prevention | 3 | Selection limit, URL validation, uncertainty |
| Recognition | 2 | Port decoding and flat column menu |
| Efficiency | 2 | Useful filters, weakened return workflow |
| Minimalist design | 3 | Restrained system; render unverified |
| Error recovery | 3 | Retry and recovery paths |
| Help/documentation | 3 | Pilot notice, evidence scope, contract |
| **Total** | **26/40** | **Core workflow needs repair** |

Cognitive load is moderate. Technical complexity is justified; avoidable burden comes from missing chunking and lost working context. The journey begins with credible caution, then loses momentum during selection and electrical comparison.

## Provisional audit health

| Dimension | /4 | Evidence |
| --- | ---: | --- |
| Accessibility | 3 | Semantic controls/focus; browser checks outstanding |
| Performance | 3 | Lean 36KB JS; 640KB index and full-table rerenders |
| Theming | 3 | Light/dark/system tokens; render unverified |
| Responsive design | 2 | Distant action and compact targets |
| Implementation integrity | 2 | Generic structure; formatting/state gaps |
| **Total** | **13/20** | **Significant work needed** |

## Strengths and persona checks

- Preserve distinct unknown, conflicted, not-yet-extracted and false states.
- Preserve field versus record evidence and explicit confidence scope.
- Two schemas support 150 chargers and four visibly fictional power strips.
- Preserve maintainer `stamp_build()` cache-busting and `main:focus:not(:focus-visible)` suppression.
- Expert users benefit from filters but lose context through return links.
- Keyboard users have selection-focus restoration but a distant comparison action.
- Phone users benefit from collapsed filters but face compact controls.
- Technical buyers must decode precisely the port and sharing facts they came to compare.

## Verification and limitations

- `node --check docs/app.js`: passed.
- `node scripts/smoke.mjs`: passed, 154 products / two categories / 161 JSON files.
- `impeccable detect --json docs`: `[]`; not a visual pass.
- URL detector at 390×844 failed: no supported Chrome/Chromium/Edge/Brave installation found.
- Browser smoke skipped: Playwright `MODULE_NOT_FOUND`.
- Context launcher failed with `approval request failed`; existing context read directly.
- No screenshot, overlay, live-server or rendered accessibility claim. No unrelated screenshots substituted.
- No ignore list. Assessments A/B sequential in delegated context. Canonical target `docs/index.html`; skill snapshot persistence skipped by read-only reviewer. Coordinator saves this requested report.
- Reviewer changed no repository files.

Fix P1 first, then return-state preservation, target sizing and column grouping; finish with `$impeccable polish` and rendered desktop/mobile checks when browser execution is available.

Questions skipped: delegated run.
