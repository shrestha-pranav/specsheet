# Power stations: A1 notes (2026-11-23)

## The opaque specs and where they actually live
- **Rated vs usable Wh.** Every store prints rated (nominal pack) energy; usable AC energy is ~80-90 % of it and is almost never printed. Profile keys
  cap.energy_wh and cap.usable_wh are separate; usable only from a row labelled usable/available (none found this round). Pack basis (51.2 V,
  29.4 Ah) goes to cap.pack_voltage_v / cap.pack_ah; Wh is never computed. Goal Zero 'Single cell equivalent capacity 421Ah @ 3.6V' and old
  'Peak Capacity' rows are other bases: left unmapped.
- **Continuous vs surge vs boost.** out.ac_continuous_w only from an AC row tagged total/rated/continuous (EcoFlow '6 outlets, 1800W total',
  Jackery 'AC Total Output 1500W Rated', SOLIX 'AC Rated Output'). Surge (ms-s, duration not printed) and X-Boost / Power Lifting (resistive loads
  at reduced voltage) are their own keys. Several untagged AC figures (BLUETTI Premium 100 V2 '2,000W Max' + '1,800W Max') stay unresolved.
- **Outlets / waveform.** Counts summed only over rows printing a count (EcoFlow DELTA Pro 3: 4 x 5-20R + TT-30R + 6-20R + L14-30R = 7).
  Waveform only from 'Inverter Type' / AC row saying pure sine wave.
- **Chemistry + cycle life.** LFP dominates (EcoFlow, SOLIX, BLUETTI, Jackery, new Goal Zero); Goal Zero Yeti X = 'Li-ion NMC', 500 cycles to 80 %.
  Cycle life carries retention_pct as a basis: Jackery rates 4000 cycles to 70 %, the others to 80 %; a count without retention is unresolved.
- **Inputs.** AC input with ac_charge_mode (turbo / standard / low speed are separate conditional claims; no headline pick). Solar: '500W Max*2'
  = per-port (in.solar_port_w x in.solar_ports), the combined figure only when printed ('dual port 1,000W', '2600W total', 'Double to 400W',
  'Total Combined DC/Solar Input 900W'). Voltage window = range with voltage_basis voc / operating / unstated (EcoFlow is unstated) and one claim
  per port when there are several. EcoFlow 'Car Charging 800W' is the Alternator Charger accessory: unresolved.
- **Recharge time.** Only with a printed charge range (Goal Zero '0-80%: 0.8 hrs', 'RECHARGE CHARGE TIMES (0-100%)'); BLUETTI/Jackery times
  have no range and stay unresolved preview claims. Condition `charger` keeps the input used.
- **UPS/EPS.** ups.switchover_ms with backup_mode (ups / eps / aps = Goal Zero 'Automatic Power Switching'); '<10ms' is an upper bound. No
  certification behind the term.
- **Expandability.** exp.expandable true from an extra-battery row, false only from 'Chainable: No'; Goal Zero 'Expansion Module Port' is a module
  bay, not battery expansion. Compatible battery names (exp.batteries) are extracted but not auto-accepted.
- **Certification.** cert.ul2743 / cert.ul9540 true only from a certification row naming the standard (7 BLUETTI models print UL2743); 'UL
  Standard' (BLUETTI AC180P) is not a listing. Title text ('(UL9540 Certificated)') is not read. UL Product iQ verification not built.
- **Idle draw**: not on any store page (manuals / bench tests). Key reserved (idle.draw_w, idle_mode basis).
