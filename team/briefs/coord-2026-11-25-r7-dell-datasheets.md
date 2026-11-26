# Brief: r7 Dell monitor datasheets (flicker + USB-C). Owner: A3-docs. Read common.md, team/reports/2026-11-25-a2-r6-dell.md, team/reports/2026-11-25-a3-r6-router-docs.md.
28 in-scope Dell monitors (mostly S/SE/U) have no flk.pwm; monitor PWM preset 76.1% (needs 396/494). Dell datasheets/spec sheets live on www.delltechnologies.com and i.dell.com (both crawl agent). 
1. Discover datasheet links from stored Dell monitor pages (raw snapshots) or Dell's own document listings allowed by robots; fetch politely (<=1 req/s, honest UA, stop on 403).
2. Parse with the existing monitor docspec parser (extend via a new module if needed, re-pin/reissue policy @N+1): flk.pwm only from explicit "Flicker-free" / "ComfortView Plus" + flicker-free / TÜV flicker-free statement; usb.* PD W, alt DP; refresh native.
3. Identity: datasheet must name the exact Dell model (e.g. "S2725DS"); multi-model sheets row-scoped only.
Report preset before/after. Do not edit source-policy.yaml unless a Dell document host is missing (then add with evidence + version bump). Do not run release.sh; finish with bare import.py --strict-parsers + build.py under flock rc 0. Finish by 17:00.
Report: team/reports/2026-11-25-a3-r7-dell-datasheets.md (<=30 lines).
