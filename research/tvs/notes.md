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

## Coordinator rulings (2026-11-24, preset fill round; A2 applied)
- **Ruling 2, backlight value table** (`panel.display_tech`): a row labelled exactly "Backlight Type" whose whole value is Full Array LED,
  Active Full Array, Mini LED, Edge(-lit) or Direct(-lit) writes `lcd` when no display-type row resolved the technology (a backlit panel is an
  LCD). "Full Array LED" / "Active Full Array" also write `panel.backlight: direct_led`. Unmapped values (Vizio "DLED", "Local Dimming") stay
  unresolved. LG "Direct" is A2's reading of the table (LED backlight rows), flagged for A1; striking it is one regex in `_tv.BACKLIGHT_LCD`.
- **4K 120 Hz ports**: LG "HDMI Input: 4ea (supports 4K 120Hz, eARC, VRR, ...)" without a trailing "(N port)" stays unresolved: the same page
  prints eARC on one port only ("eARC (HDMI 2)"), so the list is a union of port features, not a per-port statement. LG's older
  "Latest HDMI (4K @ 120Hz): HDMI ports 3,4" row is an explicit port list and is counted. TCL US pages print "4 HDMI (1 eARC)" with no rate.
- **`hdmi.has_4k120`** (coordinator ruling, 2026-11-24 round 2): affirmative-only bool, "at least one HDMI input takes 4K at 120 Hz". Set from an
  HDMI input cell (labels HDMI Maximum Input Rate / HDMI 2.1 / HDMI / HDMI Input) printing a 4K figure of 120 Hz or more, or from LG's
  "Latest HDMI (4K @ 120Hz)" port list. Never false, never a port count: `hdmi.ports_4k120` keeps the rules above. The preset
  `tv-4-hdmi-4k120` ("TVs with 4K 120 Hz HDMI") gates on this key plus a native 120 Hz panel; the port count is a column. TCL rows with no
  4K rate and every Vizio row ("HDMI Type: 2.1" names no rate) stay unknown.

## 4K 120 Hz port counts from TCL quick start guides (A2-st r7, 2026-11-26)
- New claim/document-tv-ports@1 (docspec-tv-ports@1, transform docspec-attach-tvports@1, pending): the per-port connection lines
  "HDMI port 1: Supports up to 4K/144Hz | HDMI port 2: Supports up to 4K/120Hz | HDMI ports 3 & 4: Supports up to 4K/60Hz". 13 stored TCL
  guides print them (all = 2 of 4 ports). Only guides whose text layer names the model bind (85Q651G, 98Q651G, 115QM891G, 85/98X11K, QM64L);
  QM6K / QM7K / QM8K / QM9K guides show the model range only as artwork (OCR is not read), so those rows stay unknown.
- No other lever in stored raw: LG "4ea (supports 4K 120Hz ...)" stays unresolved (ruling above); Samsung LST7D 65" / LST9T / MNA89 sizes print
  no input-rate row for that size (siblings' rows are never transferred); Vizio "Type 2.1" names no rate; LG 2026 pages link no spec sheet.
