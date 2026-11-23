# TVs: who publishes what (US, A1 2026-11-23)

Evidence base: every stored snapshot of ENERGY STAR (175 rows), Samsung (195 model codes, spec API), LG (sitemap 928 pages; 2021+ lines
fetched first), TCL (83 SKUs); per-label value histograms (team/reports/2026-11-23-a12-tvs.md). V = seen in the data, U = not verified.

## Where each profile spec lives
| Spec | ENERGY STAR | Samsung | LG | TCL |
|--|--|--|--|--|
| size class / viewable | viewable only | Screen Size / Real Inch | Size / Diagonal | Screen Class / Viewable Display Size |
| display tech (LCD/OLED) | display_type (LCD, QD-LED, OLED) | Product Type (OLED, QLED, Neo QLED, Micro RGB) | Display Type | Display Technology |
| OLED subtype (WOLED/QD-OLED) | - | - | - | - (no OLED) |
| LCD VA/IPS | - | - | Panel Type (older pages) | Screen / Panel Type (HVA, WHVA = VA) |
| backlight | Direct/Edge only | "Contrast: Mini LED" (not trusted) | Backlight Type | Mini-LED / Local Dimming Type |
| native refresh | - | Refresh Rate ("120Hz (Up to 144Hz)") | Refresh Rate ("120Hz Native (VRR 144Hz)") | Panel Refresh ("144Hz/DLG 288Hz") |
| HDMI 4K120 per port | - | HDMI Maximum Input Rate ("for HDMI 1/2/3/4") | HDMI Input "(N port)" | HDMI ("HDMI 1-2: 4K@144Hz") |
| local-dimming zones | - | - | - | Dimming Zones ("Up to 4000", "2100+") |
| HDR formats | - | per-format rows (HDR10+, HLG; no Dolby Vision row) | format list | format list |
| on-mode power | measured on-mode + DOE figure | Typical / Max | Power Consumption (basis unstated) | Power Consumption (watts) |
| weight / dims with+without stand | - | yes (some in mm under "inch") | yes | yes (inch and mm rows) |

## Hidden / gamed specs (tier core)
- Panel by size (V): one model line mixes WOLED/QD-OLED or VA/IPS across sizes; makers do not print it (TCL prints the VA family only).
- Native vs marketing refresh (V): Motion Rate 240, TruMotion 120, Motion Xcelerator 144, Clear Motion Index 480, DLG 288 Hz (half
  vertical resolution). Samsung's own "Motion Rate" row repeats 60 Hz on budget sets.
- HDMI 2.1 (V): "HDMI 2.1" on the box says nothing about how many ports do 4K120; TCL QM6K/QM7K: 2 of 4; LG QNED: "(2 port)" of 4;
  Samsung lists the ports; budget Samsung: "4K 60Hz (for HDMI 1/2/3)" = 0 ports.
- Zones (V): only TCL prints them, as "Up to N" (line maximum) or "N+" (lower bound); neither is a per-size count.
- Brightness (V): TCL "Up to 6000 Peak Nits" (no window/mode); a UHDA-method typical figure in some boxes; neither accepted as trusted.
- Power (V): the ES programme limit (maximum_on_mode_power_for_certification) sits next to the measured value; never a product fact.

## Data-quality traps seen
- Samsung spec API rows shifted by one in some groups (FreeSync holding the accessibility text, Product Type holding the resolution):
  enumerated-value checks drop them. Samsung prints 30 sets' dimensions in mm under an "inch" label (1224.6 x 707.8 x 76.6 inch):
  kept as unresolved by the size-class plausibility check, never divided by 25.4.
- 28 ENERGY STAR rows list horizontal < vertical resolution (2160 x 3840): absence, never re-ordered.
- TCL theme has two layouts (one box per size; per-variant panels with a Model row); misaligned cells ('Screen Size: 75QM9K').
- LG "Under 0.5W" standby is a bound (unresolved). LG older pages (2013-2019) use different labels; fetched last.

## Sources not used for specs
- DisplayHDR (VESA) does not apply: its certified list holds monitors/notebooks (Hisense/Sony entries are monitors); no consumer TV is listed.
- RTINGS (panel type per size, measured zones, input lag): JS-rendered, ToS; hand-curated per-model records only (open question 1).
- DOE CCMS (regulations.doe.gov certification data) also certifies TVs with on-mode power for every brand (incl. lapsed ES models): not probed
  this round; candidate second regulatory source.

## Open questions
1. Measured data (RTINGS-style panel subtype, zones, HDMI bandwidth): curated claims of kind measured with citation?
2. ENERGY STAR wildcard declarations for LG -> pattern relations (identity.md, A3).
3. Samsung E/F production letter as a panel-source marker: needs one review that reads both panels to become a rule.
