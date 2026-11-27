# smart-home identity rules (A2-home r12, 2026-11-26)
- Key: mfr_model = Zigbee2MQTT `model` as written (the maker's model id), issuer = slug of `vendor`. Same normalisation as every model importer (upper, no spaces).
- Slash lists ("E1524/E1810", "324131092621/324131092622"): Zigbee2MQTT declares the ids one device; ONE row keyed by the full string, each id a model_variant alias (preview). Never split into two rows.
- `zigbeeModel` strings (what the device reports in its Basic cluster, "TRADFRI remote control", "lumi.sensor_motion.aq2") = alias kind device_reported_model. Never a key: firmware strings are shared across regional SKUs.
- `whiteLabel` entries (Lidl HG06337 = a Tuya TS011F module) = alias kind white_label on the defining row, "<vendor> <model>". Not minted as rows this round: the white-label row has no definition of its own and its exposes come from the parent; a later A1 ruling may mint them with a rebadge edge.
- Not minted: Tuya chip/module ids (vendor Tuya + TS0xxx / TS1xxx / TS0601_*), models without a digit (names), strings > 60 chars. Counted in discovery.json checkpoint.generic.
- Two definitions with one (brand, model) (a model re-filed for a new firmware, fingerprint split): one ref; their exposes must agree for any false to be written, otherwise true-only.
- Market: Z2M is global, rows carry market null. EU-only models (Lidl, Paulmann) are in the table; a US maker-store adapter is the later US confirmation.
- CSA Matter DCL join (when reachable): exact normalised (brand, partNumber or productName) only; DCL rows are global and include kit / regional names (robot-vacuums precedent, crawler/adapters/csa_dcl_robovac.py).
