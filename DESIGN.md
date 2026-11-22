# specsheet visual system

## Authority and direction
The UI v1 brief governs this design. The incumbent's compact system-type table is useful visual authority: expand its information architecture and finish, preserving density and direct controls. This is an Operate/Read product, built directly in code. No images or decorative mockups are needed. The brief explicitly requests non-interactive design and implementation, so its supplied context replaces skill interview/confirmation rounds.

Readers compare products at a desk in daylight and revisit specifications on phones at night. Default to OS light/dark preference and offer an explicit persisted theme choice. Light surfaces are cool white and mist; dark surfaces are slate. Teal indicates actions and selection; amber indicates uncertain or conflicting evidence. Text labels always identify state.

## Tokens
- Light: background #f4f7f7, surface #ffffff, ink #172d32, muted #52656a, rule #cbd7d9, accent #006b67, accent-soft #e3f2ef, warning ink #805000, warning surface #fff3da.
- Dark: background #111c20, surface #19292e, ink #edf4f4, muted #adc0c5, rule #3a5057, accent #80ddd0, accent-soft #203f3c, warning ink #f5cf84, warning surface #3b3020.
- System UI sans for all navigation and prose; native monospace only for identifiers and literal technical data. Table numerals tabular. Body 15px/1.5; table 14px/1.45; h1 30–36px/1.15; section heading 20px. Avoid eyebrow labels and oversized hero type.
- Spacing: 4, 8, 12, 16, 24, 32, 48px. Max content width 1440px, gutters 32px desktop / 16px phone. Controls minimum 40px high; 44px touch affordances. Subtle 6px control radius; tables and document sections use rules rather than cards. No decorative shadows or gradients.
- Focus: conspicuous 3px accent outline with offset. Underline links in prose; buttons have visible hover/disabled states. Theme selection, caret and scrollbar. Reduced motion respected; only a short background transition on compare selection, no entrance animation.

## Components and layout
Compact masthead: specsheet wordmark as home link, catalogue navigation, theme control. Main hierarchy is breadcrumb, page title and description, task controls, data. A persistent unreviewed-pilot notice explains uncertainty without overwhelming results. Use simple category list rows with name, description and count, not marketing cards.

Category desktop: 224–256px filter rail to the left of the results; search/count/column controls above a semantic comparison table. At <=800px filters become a disclosure above results. Horizontal scrolling belongs only to the table wrapper; product column remains readable and names wrap. Select checkboxes and product links are distinct targets. A comparison shelf appears after selection, names selected products, permits removal, explains the 2–4 limit and links to comparison once eligible.

Product: name and identifiers lead, followed by identity caveats and notes. Grouped specification tables pair values with compact, expandable evidence details. Display field-specific citations as field evidence and fallback record citations as context only. Confidence is labeled by scope; legacy record confidence must not appear as verified field confidence. Explicit Unknown, Conflicted, Not yet extracted and Not applicable states are readable text. Lists retain known-empty meaning. Sources use human-readable host/title links, with raw URLs available. Documents and media have honest empty states.

Comparison: 2–4 products within one category, product headers and schema-grouped rows. Highlight differing values with a subtle tint and a text/legend cue; offer differences-only. Unknown and conflicted values remain distinct, never false. On phones the table scrolls horizontally within its own region. Preserve an obvious return to category results.

## Delivery choice
Plain static HTML/CSS/ES modules avoid a framework build dependency for a small read-only catalogue. Python emits versioned JSON into docs/api/v1. Hash routes and relative fetch/asset URLs work both at localhost root and GitHub Pages `/specsheet/` without rewrite rules. No external fonts or services. All user-facing data is escaped or inserted as text; source URLs accept only http(s). Async route changes must not render stale results.

## Verification
Build checks every shipped .js/.mjs and executable inline script with node --check; it fails on any syntax error. Dataset smoke checks every emitted JSON, counts, IDs, schema keys and detail/index agreement. Browser smoke checks nonempty charger rows and Anker search when Playwright is available, plus responsive layout, keyboard access, compare and explicit state behavior during review. Keep tests at port 3999 and test the deployment subpath.
