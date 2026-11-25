# Brief: coverage r4 (SSD names, monitor flicker). Owner: A2. Read common.md, D9, D10, team/reports/2026-11-25-a2-independent-sources.md.
1. Kingston NV1/NV2 name parser bug: names like "kingston.com/ssd 250GB" leak into product names. Fix in the Kingston adapter/parser, add regression test, confirm no other Kingston name contains a URL/domain fragment (grep the build output).
2. Notebookcheck (registered: kind measurement, crawl agent, quote <=100 words + visible link + name). Monitors and laptops-with-panels we carry:
   - Record measured PWM as kind measured, measurement.mode optical, with frequency Hz and brightness condition when stated.
   - flicker-free (flk.pwm = no) ONLY from an explicit "no PWM detected" / "PWM: no" statement in the review. Never derive "free" from a Hz threshold. A measured PWM Hz value is an affirmative flk.pwm = yes.
   - Identity: review must name the exact model (panel revisions differ); family-level reviews do not bind. Respect robots and ~1 req/s; discover via their site search/sitemap, not search-engine scraping at scale.
3. Lenovo user guides (download.lenovo.com / psrefstuff, crawl agent) for monitor flicker statements ("flicker-free", TÜV flicker-free cert) for monitors the monitor-PWM preset lacks. Affirmative only.
4. Report monitor-PWM preset fill before/after (currently 76.7%, gate 80%).
Constraints: new extractors land as pending @N policies; no release (RELEASE_DRY_RUN=1 only); builds under flock; no git stash. Another agent (A3 OCR) edits crawler/documents.py and _docparse.py — do not touch those; list shared-file edits.
Report: team/reports/2026-11-25-a2-coverage-r4.md (<=50 lines).
