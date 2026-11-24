# Power banks: A1 notes (2026-11-23)

## The opaque specs and where they actually live
- **Three capacities, one word.** (a) cell mAh at the cell's nominal voltage (3.6/3.7/3.85 V) = the title number; (b) rated energy in Wh =
  the only comparable figure and the airline one; (c) rated capacity at the output (5 V, sometimes '5V/9V/7A typical') = what a phone gets,
  ~55-65 % of (a). Profile keys: cap.cell_mah, cap.energy_wh, cap.rated_mah (+cap.rated_basis), and cap.class_mah for title-only '10K'.
  Wh is never computed from mAh x an assumed voltage. Seen in the wild: Anker A1657 'Battery Capacity: 5,000mAh, 7.4VDC / 37Wh (Two Cells in
  Series)' next to 'Total Capacity 10,000mAh'; UGREEN '20,000mAh/72Wh (14.4V*5000mAh)'; CUKTECH 'Cell Capacity: 74Wh/75.5Wh 7.4V'
  (typical/rated). A series-pack mAh (voltage >= 5 V in the literal) is not a cell mAh and is skipped by the parsers.
- **Airline limit** (FAA/IATA, carry-on, <=100 Wh no approval; 100-160 Wh airline approval): cap.under_100wh only from a stated Wh or a maker's
  explicit TSA statement (Belkin 'Compliant with TSA carry-on requirements'). 26,800 mAh is 96.5 Wh at 3.6 V but 103 Wh at 3.85 V.
- **PDO table** (reuses the GaN-charger pilot model: fixed 'XVYA' list + PPS 'a-bV cA' ranges, per port): out.ports list of objects
  {name, type, direction, max_w, fixed_pdos, pps}. Anker merges 'USB-C Cable / Port' into one row; INIU 'OUT1/OUT2' = each port;
  CUKTECH 'USB-A1 & Type-C1 & Type-C2' = all-ports total. A '3-11V' range on USB-A is QC/proprietary, not PPS.
- **Total vs single port vs simultaneous.** out.max_total_w = the highest total the maker prints for any port combination, or the single-port max
  when that is higher (INIU: 45 W on one port, 15 W whenever two ports are used). out.simultaneous keeps the combination literal.
  Belkin's 'Wattage' row does not say which: out.max_output_w (separate key, not comparable).
- **Input / recharge time**: in.max_w + in.pdos from the input row; recharge time is quoted with the maker's charger, often 'to 80 %'.
- **Chemistry**: only explicit words (CUKTECH/UGREEN 'Battery Type', Belkin 'BoostSolid' = semi-solid). 'Lithium-ion' covers pouch cells too.
- **Pass-through, display**: prose/FAQ phrases only (P.passthrough / P.display); absence of a phrase stays unknown, never 'false'.

## Not reachable / not done
- Cell voltage is rarely printed on store pages (label photo / manual PDF: OCR path, not built). Weight on Belkin pages: none.
- ChargerLAB measured data: see merchants.md (robots disallows ClaudeBot/anthropic-ai; prose reviews, no structured table). Not used.
- CPSC recalls: API works (saferproducts.gov RestWebServices/Recall?format=json&ProductName=power bank, 33 recalls), model numbers live in free
  text ('model W5 PRO'); adapter not built this round (safety.recall key reserved in the profile).

## Preset fill (A2, 2026-11-24): PPS and single-port output, A1 ruling 1
- **Ruling 1 (coordinator for A1, 2026-11-24): complete-enumeration negatives, narrowly.** `pd.pps` false only when the maker's own structured
  spec section prints every output port with its protocol list and none names PPS. The claim carries condition `basis: complete_enumeration`
  (profile condition + `pd.pps` basis_conditions) and keeps the per-port list as raw. Built for UGREEN only: the 'Support Protocol' block names
  each output port (`USB-C1/C2: PD3.0/...; USB-A: QC3.0/...`) and the block prints the inventory (`Ports USB-A*1 USB-C*2`); every inventory port
  must have its own list, no list may be open-ended ('etc.'). Refused: Anker fixed-PDO lists (the Prime 26K page lists no PPS range although
  a PDO list is not a protocol list), INIU 'PPS, AFC, etc.', UGREEN/INIU product-level 'Protocols' lines that do not name ports, and Belkin/mophie
  (never print PPS: stay unknown). A true claim and a complete-enumeration false on one product are two bases: resolve.py leaves it unknown.
- **PPS true** additionally from a protocol row named PPS in Anker's output section ('PPS: 65W', '[USB-C]-PPS: 3V-11V⎓2.72 (30W Max)') and from
  UGREEN per-port protocol lists. The PM's "PPS on 15 of 22 Anker pages" was the site-wide `US_PPS_collection` / 'PPS Signup' campaign strings:
  only 3 Anker pages print the protocol.
- **out.max_single_port_w** only from a figure labelled single-port (Belkin 'Wattage' '140W Single 158W Shared', 'Maximum single USB-C output',
  At a Glance 'up to 65W from a single USB-C port', '15W USB-C power maximum for single device') or the max of a per-port list where every entry
  names one port (mophie 'Output', UGREEN 'USB-C1 Output: ... USB-C2 Output: ...'). Anker pages that print only a total or PDOs without a W
  figure, and prose-only pages (A110R, A1383, A168x), stay unknown.
