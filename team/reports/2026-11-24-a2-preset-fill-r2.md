# A2 preset fill r2 (2026-11-24): coordinator rulings 1-4
**`RELEASE_DRY_RUN=1 scripts/release.sh "preset fill r2"`: rc 0.** 6 of 8 presets pass (was 4). Nothing committed or pushed. 3 policies are `approval: pending`: tvs-structured@4, mfr-routers-direct@4, mfr-ssd-sandisk-datasheet@1.

| preset (gate keys) | before | after | status |
|--|--|--|--|
| tv-4-hdmi-4k120, now "TVs with 4K 120 Hz HDMI" (refresh.native_hz; hdmi.has_4k120) | 97.0 / ports_4k120 72.1% | 97.0 / **84.6%** (291/344), LG+Samsung+TCL | **PASS** |
| router-wifi7-6ghz (generation; has_6ghz; rate_5) | 92.8 / 87.2 / 73.7% | 97.5 / 97.1 / **82.1%** (115/140) | **PASS** |
| ssd-dram-2tb (capacity; protocol; dram_type) | 88.2 / 90.8 / 54.3% | 88.2 / 90.8 / **64.0%** (238/372, need 60) | fail |
| no-pwm-usbc-monitor (flk.pwm) | 68.5% | 68.5% | fail (item 4: no new source) |
| ram-upgradable / tv-panel-by-size / purifier | pass | unchanged | PASS |
| power-bank-samsung-45w (pd.pps) | 15.6% | 15.6% | fail (not in scope this round) |

## What changed (claim diff, HEAD worktree vs new parsers, every stored snapshot: 0 removed, 0 changed)
1. **TVs** (`_tv.py`, lg/samsung/tcl/vizio_tvs@3): new affirmative-only bool `hdmi.has_4k120`. It is set from an HDMI input cell printing 4K at 120 Hz or more, or from LG's "Latest HDMI (4K @ 120Hz)" port list. Adds LG +215, Samsung +126, TCL +21. It never sets a port count and never sets false. Vizio and TCL rows with no rate stay unknown. In `docs/presets.json`, the preset filter is now has_4k120 plus a native 120 Hz panel, and the columns now include has_4k120, ports_4k120 and hdmi.count.
2. **Routers** (ubiquiti/glinet_routers@3, new `_nowifi.py`): six Wi-Fi keys are set `not_applicable`, `basis: complete_enumeration` on 9 Ubiquiti gateways and on GL.iNet Brume 2 and Brume 3.
   - Ubiquiti: the page has no `integrated-wifi` section (UDR7/UX7 carry one), has a complete Port Layout, and no row names a radio.
   - GL.iNet: the Interface row is a complete "N x" list and no Wi-Fi word appears anywhere.
   - GL-MV1000 ("Brume-W only" Wi-Fi) stays unknown.
   - Also: "802.11b/g/n" now maps to `wifi4` (+5 rows, which leave the scope).
   - I did not use the Orbi class number: no documented NETGEAR table maps it to per-band rates. The rule is written in routers/notes.md.
3. **SSDs**: new source `sandisk-us-ssd-datasheets` (`sandisk_datasheets.py`). I fetched the 35 datasheets that the line pages link, at 1 req/s with the honest UA; all returned 200. It reads only `hw.dram_type`, from a DRAM row whose single value spans every capacity column, and ties each column to a configuration through MODEL NUMBERS.
   - Yes → dram: 32 configurations (SN8100, NAS 800, Optimus GX PRO 8100/850X/850P).
   - Host Memory Buffer → dramless_hmb: 12 (Optimus 5100, GX 7100/7100M/7100X).
   - "DRAM No" → dramless: 12 SATA configurations.
   - It attaches by configuration mfr_sku only, so no new entities and no links (ssd configurations still 584).
   - SN850X, SN850P, SN7100, SN5000/5100 and SN3000 print no DRAM row, so their 60 needed values are not on SanDisk's own documents.
4. **Lenovo flicker** (item 4): lenovo.com allows /p/ in robots.txt and pages return 200 with JSON spec rows. The only related row is "Eye Caring: Yes", with no flicker statement, so nothing is read. Recorded in monitors/merchants.md.

## Shared-file changes
- registry.py: +1 source line.
- New adapters `_nowifi.py` and `sandisk_datasheets.py`.
- `_tv.py`. `_router.py` is unchanged on purpose: it is hashed into the TP-Link, NETGEAR and ASUS fingerprints.
- Profiles and notes: tvs (+hdmi.has_4k120), routers (basis condition on generation, band_count and rate_*), ssds (dram source line).
- Tests: test_preset_fill_{tvs,routers,ssds}.py.
- `docs/presets.json`.
- The build also touched docs/index.html, releases/index.jsonl and a new releases manifest.

## Open (decisions first)
1. **Policy lock entry (coordinator):** mfr-routers-direct@3 was locked by a first strict import that failed. Its parser hashes predate moving the helper out of `_router.py`. I retired it verbatim, unused, and reissued the same meaning as @4.
2. **"DRAM No" from datasheets (A1/coordinator):** I wrote it as dramless under ruling 5, since it is an explicit statement, not silence. It affects SATA drives only. Strike it if "affirmative only" meant Yes and HMB only.
3. **SSD gate:** the remaining 60 rows need a WD_BLACK SN850X / SN7100 DRAM source the maker does not print. Separately, SanDisk portable drives with unknown if.protocol still sit in the DRAM denominator; their datasheets name USB, but that is outside ruling 3.
