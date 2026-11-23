Method: dual-agent (A: /root/design_review · B: /root/audit_evidence); source and shipped-data inspection, without rendered browser verification.
# UI critique + audit — 2026-11-23

Scope: `docs/app.js`, `docs/styles.css`, `docs/index.html`, root `DESIGN.md` and `PRODUCT.md`; all six visible categories. Ranked below by buyer impact.
Verdict: the restrained, schema-led reference design fits the product. Task continuity and evidence semantics need work: finding an exact retail SKU, comparing its siblings, and understanding which claims apply must become one coherent flow.
Preserve: distinct absence states; field evidence versus record context; exact identifiers and approved parent relationships; URL-backed selection; semantic tables, theme tokens and reduced-motion handling.
Implementation integrity: fails the promised additive preview behavior despite a coherent visual system. No P0 established; P1s have workarounds but materially compromise the core task.

## P1 — fix before release, in this order

### 1. “Include unreviewed” removes trusted products
Evidence: `docs/app.js` → `indexFor()` returns preview rows instead of a union. Shipped indexes lose 2,668 trusted monitors, 368 power strips, 85 routers and 492 SSDs when preview is enabled. Some overlapping monitor rows also lose known fields; this is not just inaccurate counting.
Fix: retain every trusted row and its facts, attach preview claims separately, then append preview-only identities. In `cellValue()`, show the reviewed baseline and a text-labeled candidate beneath it; dashed styling alone is insufficient. Derive displayed counts from the resulting collection. Keep existing valid selections when toggling.
Acceptance: every trusted ID remains searchable with preview on; reviewed fields remain visible; returning to trusted mode removes only preview-only selections with an explanation. Add a union regression check for all five profile-driven categories.

### 2. Retail-title searches produce false catalogue-absence claims
Evidence: the whole-query `.includes(q)` in `renderCategory().update()` matches individual fields. `83JQ0001US` finds one record; `Lenovo 83JQ0001US` finds none. `Yoga 7i` finds none, although Intel Yoga 7 configurations exist under manufacturer names. `renderTable()` then says “Not in the catalogue yet.”
Fix: in `docs/app.js`, recognize exact identifiers within pasted titles, rank exact matches first, and match normalized tokens across brand/name/variant/identifier fields. Use only curated, evidenced retail aliases for Yoga 7i; offer uncertain candidates rather than silently asserting a model mapping. Show why each candidate matched and what identifier still needs checking.
Fix the empty state to “No match for this search,” distinguish active-filter exclusions, and offer clear filters / broader search before the product request. A failed search cannot establish absence.

### 3. The model configuration grid cannot launch a comparison
Evidence: `renderProduct()` → `.model-configs` exposes links only. The four MTMs under `lenovo-83jq` can be inspected here, but must be rediscovered and selected in category results to compare.
Fix: in `docs/app.js`, add distinct 2–4 selection controls and the existing comparison shelf to the model grid, with “Compare selected configurations.” Preserve model context, selected MTMs and preview state in return URLs. Make model/family pages explicitly non-purchasable; label configuration IDs as “MTM / part number,” not the generic “Model.”
Acceptance: open model `lenovo-83jq`, select `83JQ0002US` and `83JQ000KUS`, compare, then return without repeating selection or search.

### 4. Sibling summaries omit the differences that distinguish near-identical MTMs
Evidence: `.model-configs` considers only core/default columns and silently caps them at eight. For `83JQ`, it shows CPU, GPU and storage; recorded Windows edition and included-versus-optional pen differences are omitted. `83JQ0002US` and `83JQ000KUS` match on those displayed columns but differ on both omitted attributes.
Fix: in `docs/app.js`, compute differing fields across all schema tiers, prioritize buyer-relevant differences, and show “N more differing specifications” with expansion. Add a compact CPU / RAM / storage / display / OS / pen summary beside each MTM where known. Never infer missing display details from the model name.
In `DESIGN.md`, specify that tiering may collapse differences but must disclose their existence; an arbitrary eight-column cut cannot imply configuration equivalence.

### 5. “Differences only” hides distinct claims and overstates sameness
Evidence: `renderCompare()` signs only `[status,value]`. Shipped records `lenovo-83um0003us` and `asus-h7607ba` both store weight `1.77`, but display “from 1.77 kg” versus “1.77 kg”; the row is treated as equal. Core-only scope can also yield “No differences in the recorded schema” while other tiers differ.
Fix: in `docs/app.js`, compare normalized claim meaning, including qualifier, conditions and alternatives; account separately for preview differences. Keep evidence-only differences identifiable without treating them as hardware differences. Change the empty message to “No differences among displayed fields,” expose hidden difference counts, and persist detailed-field scope in the URL.

### 6. Trust language conflicts with the published review boundary
Evidence: `docs/index.html` universally says “Unreviewed pilot data”; category/detail/comparison copy also implies all records remain unreviewed, while profile records carry `review_scope: trusted` and preview badges imply a distinct review decision. The blanket notice defines “Unknown” as “unverified,” conflating missing knowledge with evidence confidence.
Fix: in `docs/index.html` and `docs/app.js` → `previewControl()`, `renderProduct()`, `renderCompare()` and `evidenceMarkup()`, distinguish “Accepted into catalogue,” “Unreviewed candidate,” and source type such as “Manufacturer claim.” Explain that acceptance is not independent testing. Keep legacy charger status explicit rather than applying it to every category.
Place scope beside the value: direct field source, inherited model claim, or record context; give candidate values their own source links and review label. Do not let an accepted field's source disclosure appear to substantiate the candidate beneath it. Align `PRODUCT.md`/`DESIGN.md` terminology with these meanings.

### 7. Phone tables make identity and comparison context expensive to retain
Evidence from CSS, not a rendered measurement: `.compare-table` keeps a sticky first column with a 180px minimum plus product columns at least 210px wide; another cell rule can raise that first-column minimum to 210px. At 390px, label and full value cannot fit together. Catalogue MTMs sit after Select, Brand and a minimum-230px Product column; identity is not sticky.
Fix: in `docs/styles.css` and `docs/app.js`, combine brand/name/MTM in one compact identity cell for phones, keep selection adjacent, and provide a narrow sticky identity treatment. For comparison, use a compact field label plus one readable product column or a deliberate two-product mobile layout with persistent MTM headings. Avoid nested horizontal scrolling for per-port tables where one outer scroll region suffices.
Verify 320/390/768px in both themes, long identifiers, 200% text, keyboard horizontal scrolling and touch; provide named focusable regions for product specification wrappers as already done for comparison tables. Do not claim WCAG failure solely from 44px project-target misses.

## P2 — next pass, in this order

### 8. Revision qualifications arrive after the claims they qualify
Evidence: `renderProduct()` inserts `revisionsMarkup()` immediately before Documents, after specification groups. The warning about default-revision scope appears there too. Router data has 72 model revision tables; shipped SSD data has none, so absence must not suggest stable silicon.
Fix: in `docs/app.js`, put “Hardware revisions: N recorded” and a jump/selection control beside model identity, with the applicable scope stated before specs. Keep the useful per-revision delta table and source-tier links. Show inherited versus revision-specific values locally; do not present unconfirmed inherited claims as verified for that revision. Add identifier/label-location guidance only when sourced.
For categories where revision-sensitive attributes matter, say “No revision-specific evidence recorded” when appropriate. Preserve “Nothing known beyond the model; hardware may or may not differ.”

### 9. Configuration “grouping” is decoration after sorting and pagination
Evidence: `renderCategory()` slices 50 sorted rows before `renderTable()` inserts group headers. Siblings can be separated by other models or pages; the same group heading can repeat, and a lone visible sibling loses its grouping cue.
Fix: in `docs/app.js`, offer an explicit model-grouped view that groups before pagination and sorts within groups, with matching/total configuration counts. In the flat sorted view, show parent links per row instead of headers implying contiguous groups. Always show the parent relationship even when only one configuration matches.

### 10. Product requests omit the promised handoff disclosure
Evidence: request links in `renderCategory()` and the empty state do not explain draft status, public visibility or the GitHub-account requirement, despite `DESIGN.md`. The empty-state path also trims the query before building the payload, unlike the other entry point.
Fix: in `docs/app.js`, label both actions “Prepare GitHub issue draft” and add “Public if submitted; GitHub account required. Include product information only.” Pass raw `state.q` to `missingIssueUrl()` and normalize only `query_norm`. Keep the existing deliberate-click-only handoff and avoid treating an unmatched title as a confirmed missing product.

### 11. Pagination discards keyboard focus
Evidence: Next/Previous triggers `update()`, which replaces the pagination buttons. Focus restoration handles results and shelf controls only; `scrollIntoView()` does not focus the new page.
Fix: in `docs/app.js`, retain the navigation DOM or move focus predictably to the updated page status / surviving control, with an announced page number. Verify paging forward and back without restarting keyboard navigation at the document top.

## Assessment and verification

Nielsen scores (0–4): status 3; real-world match 2; control 3; consistency 3; error prevention 2; recognition 2; efficiency 2; minimalism 3; recovery 2; help 2 — **24/40**. The principal cognitive load is remembering MTMs and inferring hidden comparison scope.
Provisional source-audit scores: accessibility 3; performance 3; theming 3; responsive 2; integrity 2 — **13/20**. Responsive scoring reflects CSS constraints, not completed viewport testing; performance is not benchmarked.
Persona checks: the retail-title buyer gets a false miss; the configuration expert must reconstruct selection; the phone reader loses identity while scrolling; the revision-sensitive buyer encounters scope too late. The emotional low point is a plausible query being declared absent rather than helped toward an exact match.
Run notes: independent A completed before B findings were synthesized. CLI `impeccable detect --json docs` returned `[]` (exit 0); zero detector findings do not validate the interactions above. Context launcher failed with “approval request failed”; existing project context was read directly. No ignore file exists under `.impeccable`.
No browser tool, installed Playwright/Puppeteer or Chromium was available; no screenshots, overlay, rendered contrast, screen-reader or touch checks were performed. No server or temporary files were created, so no cleanup was needed. Target is `docs/index.html`; slug/storage helpers and extra snapshots were omitted to honor the single-file output constraint.
Recommended sequence: `$impeccable harden` for preview/search/difference correctness; `$impeccable shape` for model comparison; `$impeccable clarify` for trust/revision/request language; `$impeccable adapt` for phone tables; rendered audit, then `$impeccable polish`.
Questions skipped: this is a bounded, report-only review; no implementation or approval is needed.
