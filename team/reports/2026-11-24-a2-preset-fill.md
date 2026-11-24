# A2 preset fill (2026-11-24): PM round-4 brief, coordinator rulings 1-5
**`RELEASE_DRY_RUN=1 scripts/release.sh "preset fill"`: rc 0** (strict import, build, smokes, all tests, size budget). Nothing committed or pushed. 3 of 8 presets pass (was 1); 15 policies land `approval: pending`.

## D8 fill per preset (PM method: docs/api/v1 product records; after = this build, equal to docs/api/v1/presets.json with A4's D8)
| preset (gate key) | before | after | status / what blocks it |
|--|--|--|--|
| ram-upgradable (mem.max; mem.soldered) | 79.6% / 86.0%, brands: Lenovo | 98.1% / 96.8%, Lenovo + ASUS | **PASS** (weakest now disp.size 91.9%) |
| tv-panel-by-size (panel.display_tech) | 65.0% (404/622) | 90.0% (560/622), 4 brands | **PASS** |
| purifier-400sqft-smoke | 94.9% | 94.9% | PASS (item 5, Levoit, not done: optional) |
| router-wifi7-6ghz (has_6ghz; rate_5) | 37.8% / 67.9% | 87.2% / **73.7%** (need 10) | fail: see open 2 |
| tv-4-hdmi-4k120 (hdmi.ports_4k120) | 71.5% (246/344) | **72.1%** (248/344, need 28) | fail: see open 1 |
| no-pwm-usbc-monitor (usbc_inputs; size_class; pd_w; flk.pwm) | 0 / 52.6 / 34.2 / 69.1% | 94.4 / 99.5 / 82.4 / **68.6%** (need 51) | fail: Lenovo PWM 60/165 (PSREF prints nothing more) |
| ssd-dram-2tb (if.protocol; hw.dram_type) | 63.4% / 40.5% | 90.8% / **54.3%** (need 96) | fail: SanDisk NVMe 30/165, needs a datasheet source |
| power-bank-samsung-45w (pd.pps; max_single_port_w) | 11.2% / 38.1% | **15.6%** / 46.4% | fail: Belkin/mophie never print PPS (needs a cleared PDO source) |

## What changed (claim diff old vs new parsers over every stored snapshot; 0 removals except where noted)
1. **TVs** (`_tv.py`, lg/tcl/vizio/samsung_tvs@2): ruling 2 backlight table (whole-cell Full Array LED / Active Full Array / Mini LED / Edge / Direct -> lcd when no display-type row resolved it). LG +166, Vizio +92 (+86 backlight direct_led), TCL +4. LG "Latest HDMI (4K @ 120Hz): HDMI ports 3,4" counted (+50, mostly discontinued).
2. **Laptops** (lenovo_psref@3, asus@2): PSREF platform-prefixed Max Memory cells ("Arrow Lake: up to 64GB") normalise (177 values); ASUS +315 mem.max, +302 mem.soldered from the Memory cell's own statements (WIDENING of asus-techspec-typed).
3. **Routers** (`_router.band_enum`, all 5 parsers bumped): has_6ghz true from a listed 6 GHz band; false only from a complete band row, `basis: complete_enumeration`, list kept raw (+155 false incl. NETGEAR 8, +21 NETGEAR true); NETGEAR per-band rates from "WiFi Bands" rows.
4. **Monitors** (new `_monports.py`, lg_us@2, asus_monitors@2, lenovo_monitors@3, benq_monitors@2): usb.usbc_inputs from full port lists (0 only by complete enumeration, voided if USB-C appears anywhere else on the page); gen.size_class stated, else derived round-half-up (ruling 3, `kind: derived`, locator.derivation). BenQ: 61 diagonal-as-class values replaced by the derived class.
5. **SSDs** (`_ssd.py`, all 4 parsers bumped): ruling 5 (table "DRAM-less"/"None" -> `dramless`, HMB unknown; TEAMGROUP 122 dramless_none -> dramless); ruling 4 portable `if.protocol: usb` affirmative-only (+116); product-name nvme/sata for SanDisk/Samsung rows without an Interface row.
6. **Power banks** (all 9 parsers @5): labelled single-port W for Belkin (+6) / mophie (+7) / UGREEN; PPS true for Anker (+2) / UGREEN (+5); UGREEN +2 pd.pps false by complete per-port protocol lists. The PM's "PPS on 15 of 22 Anker pages" was site-wide campaign strings; 3 pages print the protocol.

## Policies (data/decisions/policies.yaml; all new ones pending; superseded versions moved verbatim to retired_policies + `retired:` line; import wrote the lock lines)
New: claim/mfr-structured-datasheet@3, asus-techspec-typed@3, mfr-monitor-structured@4, mfr-monitor-benq@2, mfr-routers-structured@3, mfr-routers-class@3, mfr-routers-direct@2, mfr-ssd-structured@5, mfr-ssd-samsung@3, mfr-ssd-kingston@3, mfr-power-banks-structured@7, mfr-power-stations-structured@4 (pin only: stations import shopify_powerbanks), tvs-structured@3 (+vizio display_tech), rel/source-stated-hierarchy@5, rel/bundle-contents@4 (pins only).

## Shared-file changes
crawler/adapters/_tv.py, _router.py (now imports _contract), _ssd.py, new _monports.py; 25 adapters version-bumped. A1 profiles + notes.md (rulings recorded): tvs, routers, monitors, ssds, power-banks (new `basis` condition in routers/monitors/power-banks; ssds `if.protocol` enum +usb), laptops (traps only). New tests: tests/test_preset_fill_{tvs,laptops,routers,monitors,ssds,powerbanks}.py. Smoke/test pins on old data: scripts/frontend-smoke.mjs (the live "no-pwm-usbc-monitor is 0% on usbc_inputs" assert became data-independent + a synthetic 0%-fill case; A4 please review), tests/test_adversarial.py (router policy family >= @2), tests/test_review3.py (power banks @7). Not touched: scripts/presets.py, registry.py, data/source-policy.yaml, docs/. No network fetches.

## Open (decisions first)
1. **4K120 TVs cannot pass on maker pages.** LG "HDMI Input: 4ea (supports 4K 120Hz, eARC, VRR...)" (about 50 current rows) is a union of port features: the same page prints "eARC (HDMI 2)", so it never says every port takes 4K 120. TCL prints "4 HDMI (1 eARC)" with no rate. Needs a per-port source (LG spec sheet / manual) or an A1 ruling.
2. **Router rate_5**: 9 Ubiquiti + ~8 GL.iNet wired gateways sit in scope with unknown generation (no maker row says "no Wi-Fi"), plus 19 NETGEAR Orbi pages printing only the class number. Needs an A1 not_applicable rule for radio-less gateways.
3. **For A1 review**: LG "Backlight Type: Direct" -> lcd is A2's reading of the ruling 2 table (165 LG values; one regex in `_tv.BACKLIGHT_LCD`). LG monitor Input/Output group treated as a complete enumeration (114 zeros). Vizio "DLED" left unresolved.
4. SanDisk datasheet host (documents.sandisk.com) has no data/source-policy.yaml entry. Samsung SSD gen.capacity is still not accepted by policy (0/49).
