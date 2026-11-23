# Air purifiers: A1 notes (2026-11-23)

## The key opacity: whose CADR is it?
- AHAM AC-1 defines CADR (smoke / dust / pollen, cfm; PM2.5 added for ENERGY STAR V3). Three different parties publish it:
  1. ENERGY STAR (EPA) certification, reported through a recognised certification body: `cadr_basis: energy_star_certified`.
  2. AHAM Verifide (AHAM's own third-party programme; directory at ahamdir.com). Not reachable (merchants.md), so we never mark a figure
     "AHAM verified" ourselves; a maker page that affirmatively says so gives `aham_verified_maker_stated` (Winix: an "AHAM Verified Room
     Size" row or AHAM in its Certifications row; Levoit Sprout: "Certified: Aham Verifide").
  3. Anything else: `maker_claimed`. Levoit's bare "CADR: 231 CFM" names no pollutant -> `cadr.unspecified_cfm`, never smoke.
- basis_conditions means a certified and a claimed figure that differ show as two alternatives with no headline.
- Pollen is capped at 450 in AHAM reporting: Winix prints ">450" -> unresolved, the other two kept.

## Room size
- AHAM 2/3 rule: smoke CADR >= 2/3 of floor area (8 ft ceiling). ENERGY STAR room size = smoke CADR x 1.55 (~4.8 ACH) ->
  `room_basis: energy_star_formula`. Winix "AHAM Verified Room Size" and Levoit "(4.8 ACH)" figures land in the same key with their basis.
- "Covers up to 1,718 ft2" = 1 air change per hour: `room.coverage_sqft` with the stated ach (Levoit) or none (Winix "Maximum Room Coverage").

## HEPA
- ENERGY STAR defines "HEPA" = True HEPA (>= 99.97 % at 0.3 um); "HEPA-Type" = not demonstrated. 16 of 209 ES models say HEPA.
- `filter.true_hepa` is true only on an affirmative statement and never false; HEPA-type wording is `filter.hepa_class: hepa_type`.
- `filter.hepa_grade` (H13...) only when printed as a grade; no adapter emits it yet.

## Ozone / CARB
- California requires certification of every indoor air cleaning device (UL 867 / 507 electrical safety; electronic devices also ozone
  tested to <= 0.050 ppm). The list says Mechanical (filtration only) or Electronic (ionizer / PlasmaWave / UV / electrostatic).
- `ozone.carb_certified` true only from the list, quote names EO number and date notified. Not on the list = unknown.
- A maker "CARB" badge (Winix Certifications row) is `cert.maker_listed`, preview only.

## Noise and power
- Noise needs its speed: `fan_speed` condition; printed ranges give `range_min` / `range_max` (speeds unnamed). Distance/weighting never
  stated by Levoit/Winix (Coway prints dB(A)), so cross-brand dB are not comparable measurements.
- ENERGY STAR publishes CADR/W, IEF and annual kWh but no watts; watts are never derived. Levoit "Rated Power" = nameplate
  (`power_basis: maker_rated`); per-speed watts (`pwr.speed_w`) need manuals (not built).

## Filters
- Part number only from the maker's own pairing: ENERGY STAR replacement_model_number_N (rarely filled: 4 models) and Winix's Replacement
  Filter tab (11 models). Price = the store's displayed price, list vs sale from its own labels, dated by observation; preview only.
- Filter life: Winix "(12M)" per stage. Levoit/Coway print it in manuals or prose (not parsed).
