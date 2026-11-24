# Brief: spec-profile additions for the top-10 demand questions (PM round 2). Owner: A1. Read common.md + product/demand-survey.md.
Why: product/demand-survey.md section 2 lists the 10 questions people and agents ask. Most keys already exist; these do not.
Edit only `research/<cat>/spec-profile.yaml`. Follow the provisional format. Each new key needs why/traps/sources.
1. **Laptops**: add `disp.pwm` (bool), `disp.pwm_freq_hz`, `disp.pwm_threshold_pct` (the brightness above which flicker stops).
   Sources: PSREF lists "PWM dimming" on some OLED panels (e.g. P14s Gen 5 AMD spec PDF); reviews (Notebookcheck) are secondary.
   Add `port.usbc_list` sub-fields if missing: per port {side, usb_gbps, dp_alt, tb_usb4, pd_in, pd_out_w}. Add `pwr.min_pd_w`
   (lowest charger the maker supports). Mark `mem.soldered`, `mem.slots`, `disp.panel_type`, `disp.nits_sdr`, `disp.refresh` as
   `tier: core`, so the build's coverage report flags them.
2. **Power banks + GaN chargers (shared)**: add `pd.pdo_table` (type: list of objects {port, kind: fixed|pps|avs, v_min, v_max, a_max})
   and the derived `pd.samsung_sfc2` (bool: PPS covering 9-11 V at >= 4.5 A on any port; derived, never claimed). Add `pd.ufcs` (bool).
   Note the trap: regional variants (Global vs CN) differ in PPS, so these keys are per variant.
3. **TVs**: confirm `panel.lcd_type` and `hdr.dimming_zones` are per **size variant** (not per family), with a trap note that
   "up to N zones" series claims are family ceilings and must be stored as `hdr.dimming_zones_max_claim`, not as zones.
4. **Routers**: add `hw.soc` (text), `hw.wifi_chip_<band>`; confirm streams/width keys exist for each band, including 6 GHz.
   Identity note: hardware version (v1/v2) is part of the key (coordinate with A2 identity.md).
5. **SSDs**: `hw.hmb_support` exists. Add the enum value `dram_type: none_hmb | none | ddr4 | lpddr4 ...` if it is not already
   explicit. Add `hw.revision_note` (text: known component swaps by date code/firmware).
6. **Air purifiers**: derive `filter.cost_per_year_usd` = price_usd * 12 / life_months (derived, keep inputs); add
   `cadr.verified_source` enum (aham|maker_claim). The UI must never show a maker claim as verified.
7. **Next-3 categories** (draft only, no crawl): `research/usb-c-docks/spec-profile.yaml` (per-port PD/DP/USB, MST, DSC, max displays
   per host OS, host-power W), `research/mini-pcs/` (reuse the laptop keys: mem/stor/port/net + oculink), `research/headphones/`
   (codecs, multipoint, ldac_with_multipoint, anc, battery_h_anc_on, fcc_id). Identity levels per category.
Report team/reports/2026-11-24-a1-coverage.md (<=60 lines). No crawling of new categories this round.
