# A4 site-legal report (2026-11-24)
frontend-smoke (new cases below) and smoke.mjs pass; browser-smoke skipped (no Playwright). One transient 404 in a run came from another agent rebuilding docs/api; rerun passed.
- Licences: LICENSE (Apache-2.0, "specsheet contributors"), DATA-LICENSE.md (ODbL, facts unclaimed, US federal public domain, attribution line, docs CC BY 4.0), README License section, .github/workflows/gitleaks.yml.
- One config, docs/site.json: brand ("specsheet"), domain ("knownspec.com" placeholder, not bought), site_url, repo, role contacts, api_origin (empty), legal_status. Edit it and run build.py.
- Pages (docs/pages.js): #/terms #/privacy #/sources #/about, each "Draft pending owner review". Payments text only "paid tier coming later". Sources page generated from data/decisions/policies.yaml (docs/sources.json, 45 ids); takedown legal@, 3 business days.
- Footer on every view: Terms · Privacy · Sources · corrections@ · GitHub. "Or email corrections@" added beside the GitHub issue links.
- Discovery (scripts/site_meta.py -> docs/, not docs/api): llms.txt (API/MCP marked preview), sitemap.xml, robots.txt, Dataset JSON-LD in index.html (ODbL, distribution = manifest).
- Miss beacon: sendBeacon(api_origin + /v1/miss) debounced, only when api_origin set (off now).
- scripts/requests_weekly.py: gh read-only + --misses -> team/queue/requests.md, drafts close-outs, posts nothing (tested with fixtures).
- Certification-only (extra task): flat toggle "Include certification-only listings (N)", off by default, URL param certonly=1, only where categories[].certification_only exists; preview rows with in_trusted and no base are skipped, never "unreviewed"; detail note for index_scope certification_only. Smoke cases added for all of it, plus legal pages.
Shared-file edits: scripts/build.py (stamp hashes pages.js/site.json/sources.json; main() calls site_meta.generate()), docs/index.html (rewritten, was whitespace-padded), app.js, styles.css, frontend-smoke.mjs. Not touched: docs/api, api-worker.
Notes: release_manifest.py SOURCE_DIRS omits pages.js/site.json (coordinator may add). Worker's own llms.txt should also say "paid tier coming later". Sitemap category URLs are hash routes (as briefed). Source credits are generic per brand: owner review should check DisplayHDR/Lenovo wording.
