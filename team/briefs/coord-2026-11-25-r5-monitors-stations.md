# Brief: round r5 monitors + stations. Owner: A2-mon. Read common.md, team/reports/2026-11-25-a2-r5.md, 2026-11-25-a2-zero-keys.md.
1. Monitor flicker (79.2%, gate 80%, need +4 in-scope rows): LG/BenQ stored pages — feature badge lists and image alt text naming a flicker-free certification (UL/TÜV "Flicker Free" with model on that page). Affirmative only. Exact-model binding.
2. usb.kvm on LG (342 raw files) and BenQ (175) mention KVM: emit only from the maker's spec row/feature list for that SKU.
3. res.refresh_native for LG and ASUS: only explicit native/single rate; "up to"/"Max"/OC => nothing.
4. Power stations: station-lfp-1kwh 78.7% — find chemistry (LFP/LiFePO4) statements in stored maker spec rows for in-scope stations lacking it.
5. UPS switchover ruling (coordinator, as A1): ups.switchover_ms may come from prose ONLY when (a) the page is single-SKU, (b) the sentence is in the maker's spec/feature section (not a comparison table naming other models), (c) it states a number + ms and "UPS"/"switchover"/"switch time". "<" or "within" => value with qualifier max. Multi-product comparison tables: skip.
6. Dell monitors: scout dell.com monitor spec pages (robots, ToS). If crawlable, write adapter for current US monitors (flk.pwm, usb.*, res.*); otherwise record blocked.
New/reissued extractors pending @N (retire old verbatim). Re-pin any policy whose fingerprint moves. Do not edit data/source-policy.yaml (A2-hosts owns it; ask in report for new domains — dell.com is listed? check). Do not run release.sh; bare builds under flock with --strict-parsers must pass at the end. Fixtures that look like secrets need '# gitleaks:allow'.
Report: team/reports/2026-11-25-a2-r5-monitors-stations.md (<=40 lines), preset before/after.
