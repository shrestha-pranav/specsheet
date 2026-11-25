# Coverage audit (scripts/coverage_audit.py)

Fill = share of trusted rows (entities with >=1 accepted claim) holding an accepted known value; preview counts candidates too.
Item fields (`out.ports.pps`) = at least one port row states the field. Regenerate: `python3 -I scripts/coverage_audit.py --md team/queue/coverage-audit.md`.

## Focus keys (presets + demand survey)

| category | key | trusted | preview | before (trusted) |
|---|---|---|---|---|
| chargers | pd.pps | 8.5% (12) | 8.5% | 7.0% (10) |
| chargers | out.ports.pps | 4.2% (6) | 4.2% | 2.1% (3) |
| chargers | out.ports.fixed_pdos | 27.5% (39) | 27.5% | 25.4% (36) |
| chargers | pd.pps_max_voltage | 4.2% (6) | 4.2% | 2.1% (3) |
| chargers | pd.max_fixed_voltage | 28.2% (40) | 28.2% | 25.4% (36) |
| power-banks | pd.pps | 19.1% (32) | 19.1% | 19.1% (32) |
| power-banks | out.ports.pps | 5.4% (9) | 5.4% | 5.4% (9) |
| power-banks | out.ports.fixed_pdos | 40.5% (68) | 40.5% | 40.5% (68) |
| monitors | flk.pwm | 22.9% (915) | 22.9% | 22.9% (915) |
| monitors | usb.usbc_pd_w | 8.1% (324) | 8.1% | 8.1% (324) |
| ssds | hw.dram_type | 52.4% (306) | 52.4% | 52.4% (306) |
| laptops | mem.size | 93.4% (2259) | 100.0% | 93.4% (2259) |
| tvs | hdmi.has_4k120 | 26.4% (362) | 26.4% | 26.4% (362) |
| routers | wifi.band_count | 76.3% (255) | 76.3% | 76.3% (255) |

## Evidence on hand but unparsed

| category | docs linked | skipped | not fetched | fetched, no parser/text | parsed | entities w/ doc | proposals | unmapped labels (occ.) |
|---|---|---|---|---|---|---|---|---|
| (unbound) | 61 | 61 | 0 | 0 | 0 | 0 | 0 | 0 (0) |
| air-purifiers | 36 | 2 | 34 | 0 | 0 | 0 | 0 | 263 (895) |
| chargers | 40 | 11 | 3 | 0 | 26 | 10 | 16 | 79 (436) |
| laptops | 30 | 1 | 29 | 0 | 0 | 0 | 0 | 70 (681) |
| monitors | 20 | 4 | 16 | 0 | 0 | 0 | 0 | 1341 (51891) |
| power-banks | 43 | 25 | 0 | 0 | 18 | 7 | 36 | 30 (141) |
| power-stations | 64 | 1 | 63 | 0 | 0 | 0 | 0 | 246 (601) |
| power-strips | 980 | 391 | 411 | 178 | 0 | 0 | 0 | 3 (5) |
| robot-vacuums | 53 | 0 | 53 | 0 | 0 | 0 | 0 | 213 (1774) |
| routers | 135 | 1 | 134 | 0 | 0 | 0 | 0 | 16 (640) |
| ssds | 177 | 93 | 84 | 0 | 0 | 0 | 0 | 0 (0) |
| tvs | 343 | 14 | 329 | 0 | 0 | 0 | 0 | 1515 (70368) |

Image-only spec candidates (gallery images named spec/param/label, never OCR'd), by crawl.py v0 store: anker 1617, spigen 12, ecoflow 9, belkin 2

## Lowest-filled core keys per category (trusted)

- **air-purifiers** (1142 rows): gen.brand 0%, noise.db 2%, filter.true_hepa 3%, cadr.dust_cfm 18%, cadr.smoke_cfm 18%, room.size_sqft 19%, ozone.carb_certified 96%
- **chargers** (142 rows): gen.form_factor 0%, pd.pps 8%, out.max_total_w 25%, phys.weight 25%, out.max_single_port_w 25%, in.type 31%, out.ports 31%, out.usb_c_count 44%
- **laptops** (2419 rows): disp.gamut 0%, gen.platform_variant 0%, gpu.tgp 0%, gpu.type 0%, port.tb_usb4 0%, stor.soldered 0%, disp.refresh 65%, stor.slots 69%
- **monitors** (4003 rows): gen.brand 0%, gen.hw_revision 0%, gen.region 0%, hdr.dimming_type 0%, hdr.dimming_zones 0%, motion.gtg_basis 0%, panel.vendor 0%, res.refresh_native 0%
- **power-banks** (168 rows): cap.under_100wh 0%, gen.brand 0%, gen.form_factor 0%, safety.recall 0%, bat.chemistry 5%, cap.energy_wh 15%, pd.pps 19%, out.max_total_w 22%
- **power-stations** (71 rows): gen.brand 0%, cert.ul2743 10%, exp.expandable 32%, out.ac_outlets 48%, in.ac_w 56%, cap.energy_wh 83%, bat.cycle_life 85%, in.solar_w 85%
- **power-strips** (538 rows): surge.vpr_lg 0%, surge.vpr_ln 0%, type.kind 0%, usb.total_w 19%, usb.ports 20%, safety.auto_shutoff 32%, load.max_watts 49%, surge.vpr_max 59%
- **robot-vacuums** (144 rows): gen.brand 0%, mop.type 18%, dock.mop_wash 26%, dock.self_empty 33%, nav.obstacle_sensors 35%, nav.type 36%, clean.suction_pa 47%, phys.robot_height_mm 87%
- **routers** (334 rows): gen.brand 0%, mesh.backhaul_types 0%, sup.eol_policy 0%, sup.hardware_version 0%, sup.hardware_versions 0%, sup.security_updates_until 0%, gen.pack_count 4%, hw.soc_model 5%
- **ssds** (584 rows): compat.ps5 0%, gen.brand 0%, gen.product_line 0%, id.part_numbers 0%, id.revision_marker 0%, perf.post_cache_write 0%, perf.slc_cache_size 0%, therm.heatsink 0%
- **tvs** (1371 rows): gen.brand 0%, panel.oled_subtype 0%, panel.lcd_type 3%, hdmi.has_4k120 26%, hdmi.ports_4k120 27%, vrr.supported 44%, hdr.formats 47%, pwr.on_mode_w 55%
