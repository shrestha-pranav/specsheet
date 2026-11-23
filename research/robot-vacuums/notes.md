# Robot vacuums: who publishes what (US, probed 2026-11-23)

Evidence: 84 model bundles fetched and parsed (Dreame 41, Roborock 35, Narwal 8; 125 product-JSON + 84 page requests). Profile: spec-profile.yaml
(43 specs, 9 groups). Probes of 9 more makers are in manufacturers.yaml. "V" = seen in fetched pages; unmarked = analyst judgment.

## Claim origin (the opacity problem)
- **Every number on a store page is a manufacturer claim.** Dreame is the only maker that states a basis: "*19,000Pa ...: Based on our in-house lab data"
  (V, 11 of 28 Dreame suction claims carry it -> claim_basis mfr_in_house_lab); the rest are mfr_unstated. "Certified by TÜV SÜD" appears for tangle
  claims, never for suction or noise (V), so no suction claim is third_party_certified. Roborock and Narwal print no basis at all.
- **Suction Pa is not comparable across brands** (no standard: sealed vs open inlet, at the fan vs at the brush, boost vs normal). It is kept as
  "what the maker states" with its basis, faceted, and labelled "claimed". A measured basis (sealed-inlet, RTINGS/Vacuum Wars) would be a separate
  assertion (claim kind measured, claim_basis independent_measured) shown as an alternative, never averaged.
- **Runtime and noise** are quoted for the quietest mode (V: "up to 220 minutes ... in Quiet Mode", "Lowest Noise"); both carry power_mode. Only one
  Dreame page each prints them in the spec block: candidates, not trusted.
- **Battery**: mAh only, never voltage or Wh (V, all three makers). Wh is not derived (4S 14.4 V is typical but not printed).
- **Matter**: one Dreame page ('Matter Connectivity ✓'). Roborock Qrevo Edge says Matter "will be available through an upcoming OTA" (V): not support.
  The CSA DCL ledger is the certification-grade source (not built).

## Publishers
- **Dreame (V)**: the most complete table (suction + basis, tanks, mop lift height, single-step threshold, nav + obstacle sensor type, dock wash
  temperature, hot-air dry). Four templates plus a 2-model comparison; 13 of 41 pages have no table (GoVac Amazon-line models, older L10s, X30/X40 Master).
- **Roborock (V, thin)**: the US store prints only weight, dimensions and battery in a table; suction and hot-water temperature are Key-Features bullets
  (kept as preview candidates). Robot+dock cells are mislabelled as robot (bounded out, see the profile traps).
- **Narwal (V, thin)**: one of 8 pages has a table.
- Shark blocked (robots.txt 403). Ecovacs, MOVA, eufy, SwitchBot, Lefant: no spec table in server HTML. iRobot: real model codes, thin table, no
  crawlable product list.

## Results (claim/mfr-robovac-structured@1, approval pending)
60 trusted model rows (Dreame 28, Roborock 31, Narwal 1) + 54 preview rows; 683 accepted claims, 89 candidates; 20 models are identity-only (no spec
block) and are not published. Accepted coverage: battery 55, robot height 54, dock size 41, suction 29 (Roborock's 29 suction claims stay preview),
dustbin 28, obstacle sensors 17, nav type 14, mop type 11, Matter 1.

## Deferred / needs a human
- iRobot discovery (product list is client-side; model codes in URLs are the best identity in the category).
- Ecovacs spec API (XHR) and MOVA compare data (client-rendered): need an XHR probe, not plain HTML.
- Roborock global spec pages / manuals for nav/mop/tank specs; label model codes via FCC (terms unknown).
- Independent measured suction/noise (RTINGS, Vacuum Wars): licence decision.
- CSA Matter DCL for certified Matter support.
