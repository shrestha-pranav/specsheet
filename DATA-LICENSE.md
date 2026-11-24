# Licences: code, data and documentation

DRAFT (2026-11-24, PM round 3; decision D1 in `product/decisions.md`). Pending the owner's legal review.
This file says which licence applies to which file or output, and what we do **not** license.

## Which licence covers what

| What | Where | Licence |
|---|---|---|
| Source code | `scripts/`, `crawler/`, `api-worker/` (except data it bundles), `tests/`, `schemas/`, `systemd/`, `.github/`, `docs/*.js`, `docs/*.css`, `docs/*.html`, `docs/favicon.svg` | Apache-2.0 (`LICENSE`) |
| The database (see below) | `docs/api/**`, release/bulk/API/MCP data output, `data/**`, `releases/**` | ODbL 1.0, limited as described below |
| Documentation and prose | `*.md` files (`README.md`, `ARCHITECTURE.md`, `DESIGN.md`, `PRODUCT.md`, `product/`, `research/`, `team/`, `reviews/`, `briefs/`), the text of the site pages (`#/terms`, `#/privacy`, `#/sources`, `#/about`), `docs/llms.txt` | CC BY 4.0 |
| Third-party material | quotations and URLs in `research/` and `reviews/`, product and brand names, certification marks, npm dependencies of `api-worker/` | Not ours. Each keeps its owner's rights and licence. Dependencies keep their own licence and notice files. If we distribute a bundle, those notices go with it. |

Where a file holds both code and prose (for example `docs/pages.js`), the file is Apache-2.0 and its displayed
text is also available under CC BY 4.0.

## The database: what ODbL covers and what it does not

We offer the specsheet database under the Open Database License 1.0
(<https://opendatacommons.org/licenses/odbl/1-0/>, full text there). The grant covers **only rights we hold**:

1. **The compilation.** Its selection and arrangement, its structure and schema, the product identity
   decisions (which listings are the same product, our ids, crosswalks and tombstones), review decisions, and the
   notes and derived fields we wrote.
2. **Values from sources with recorded permission evidence.** These are the sources marked `licence_grant: true`
   in `data/source-policy.yaml`. Today that is one source: U.S. EPA ENERGY STAR data (data.energystar.gov), which EPA
   publishes under its data licence. The policy file records the evidence and the conditions of use.

**What is not covered.** A value whose only sources are marked `licence_grant: false` is shown as a fact with a
link to its source, and we grant no licence over it. That covers maker spec pages, Lenovo PSREF, the VESA
DisplayHDR list, the CSA ledger, CARB, and any source not yet reviewed. We make no claim about what the source's
own terms allow. If you reuse those values, check the linked source's terms yourself. Every release's
`manifest.json` names the policy version used, and every value lists its sources, so you can tell which is which.

We do not republish marketing text, images, PDFs or page text from any source. Product, brand and certification
names belong to their owners and appear only to identify products.

### What ODbL asks of you (summary; the licence text governs)

- **Attribution** on public use of the database, a derivative database, or a produced work (a chart, table, app
  or model answer):
  > Data: specsheet (ODbL), sources linked per value

  The brand in that line follows the site (`docs/site.json`). Link to the site when you can.
- **Share-alike** for adapted databases that you use publicly. A produced work that you make public from an
  adapted database can also oblige you to offer that adapted database, or the means to recreate it (ODbL
  sections 4.4 and 4.6). Attribution alone is not always enough.
- **Commercial use is allowed** under ODbL, resale included. We do not restrict it.
- Keep the source attributions that the policy file requires, for example "Source: U.S. EPA ENERGY STAR".

### A future alternative licence

A later commercial licence (for example one without share-alike) could cover only what we can grant: point 1 above,
point-2 values whose source terms allow relicensing, and contributions whose contributors have granted us those
rights. It could not cover values from sources with `licence_grant: false`. Corrections and contributions will need
contribution terms that permit this before any alternative licence is offered. That question is with the owner's
legal review.

## Takedown and corrections

Rights holders can ask for a value, a field or a source to be removed. Write to the legal address on the Sources
page (`#/sources`). Process and timings: `product/takedown-runbook.md`. Corrections: open a GitHub issue or use the
corrections address on the site.
