# Brief: label/spec-image OCR + mophie manual binding. Owner: A3 (document pipeline). Read common.md, D9, D10, team/reports/2026-11-24-document-pipeline.md, team/reports/2026-11-25-doc-review6-fixes.md.
Goal: raise power-bank / charger pd.pps + PDO coverage from maker-published images and manuals, without loosening identity binding.

1. Anker spec images (~1,617 image URLs in raw Anker snapshots: spec/infographic images on product pages).
   - Discover from existing raw snapshots only (no new page crawl). Fetch politely (<=1 req/s, robots, same CDN host already in source-policy or a document_host entry; if a host is unlisted, list it in your report, do not add it yourself).
   - OCR with tesseract (preprocess: grayscale, upscale 2x; record per-word confidence). Feed text into existing _docparse.py PDO/PPS parser.
   - Identity: an image inherits the linking page's entity ONLY if the page is single-SKU (one model id, no variant selector covering other SKUs) — otherwise require the model number OCR'd in the image with conf >=60, per the review-6 rules. Mean OCR conf on the value tokens >=70 else drop. Never attach a value whose OCR'd voltage/current pattern is ambiguous (e.g. "3.3-11V" vs "3.3-1 1V").
   - kind stays official (maker image), source tier manufacturer, linked_from = page URL. New extractor id, new pending policy @N.
   - Fixtures: A2667 (known PPS 3.3-16V 3.25A must corroborate, not conflict), one multi-SKU page that must NOT attach, one low-conf image that must drop.
2. mophie manuals: bind via linking product pages (www.mophie.com is listed maker). Same identity guard; per-edge linked_from.
3. Run scripts/coverage_audit.py before/after; report pd.pps fill change on the power-bank preset (PB PPS currently 16.3%) and chargers.
Constraints: no release (dry run only: RELEASE_DRY_RUN=1 scripts/release.sh), builds under flock, no git stash. Shared-file edits minimal and listed.
Report: team/reports/2026-11-25-a3-ocr-mophie.md (<=50 lines): numbers, new policies, false-positive spot check (>=20 attached values checked against image), open questions.
