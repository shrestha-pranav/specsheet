# A3-fix: Codex review-9 fixes (2026-11-26)
Impact on the published build (full scratch import with new code vs the pre-change state/specsheet.sqlite, accepted claims, entity/key groups):
- P1-1 TV ports: 34 -> 28. 6 dropped: 115QM891G (no independent hdmi.count), 85X11K + 98X11K (one X11K guide names both sizes). 0 changed.
- P1-2 SFC-derived PPS: 0 dropped / 0 changed (the 1 published derived claim, Anker A1638, is an own-output sentence and stays).
- P1-3 UPS switchover: 0 of 25 changed (no stored row/prose uses a trailing bound, between-range, lower bound or approx qualifier).
- P2 Dell: 16 platforms, 44 published claims change: 16 usbc_list structured -> literal; withheld 14 video_out, 9 tb_usb4, 5 charge_port.
  The connector-unknown entries are real ("1 USB 3.2 Gen 1 (5 Gbps) port", "2 USB 3.2 Gen 2 (10 Gbps) ports with Power Delivery and DisplayPort").
  That last one is probably Type-C, and the old code skipped it as Type-A.
- P2 AOC: 164 -> 7 res.refresh_native (157 absence-based withheld). These 157 WERE in the local docs/api build (claim/mfr-monitor-aoc@2 accepts even while pending).
- P2 naming: 0 SSD/laptop names change.

Coordinator: 8 policies reissued with approval pending (locked by the bare import). Each old version was moved verbatim to retired_policies with a retired line:
claim/mfr-power-banks-structured@9, claim/derive-samsung-sfc2-pps@2, claim/mfr-power-stations-structured@9, claim/document-tv-ports@2,
claim/mfr-laptop-ports@3, claim/mfr-monitor-aoc@3, rel/bundle-contents@9, rel/source-stated-hierarchy@15.
I put the Dell guard in dell.py (`connectors_stated`), not in _xports.py, so asus/surface/asus_routers fingerprints and 3 more policies stay as they are.

Fixes:
1. `_docspec_tvports` @2: any "HDMI port(s) N:" statement the rate pattern does not read voids the list. Every fact carries n_ports.
   `docspec_r7tv` @2: emits only if the entity has exactly one official non-document hdmi.count == n_ports, so a partial prefix emits nothing (not even 0).
   The full identifier must be quoted (a series token is not enough). The linked-model exemption is removed: a guide naming any other same-brand model binds nobody.
2. `pb_pps_r7.sfc2(text, model)` @7: the whole sentence must be an affirmative output statement. Rejected: negation, questions (?, does/can.., Q:),
   input/recharge/adapter/charger context, other/another/unlike wording, and foreign model tokens (Galaxy/iPhone/Pixel N exempt). Anker passes its model.
3. `_powerstation._qualify`: trailing "max/maximum/or less/or below/at most" -> up to N. "between/from N and/to M", "N/M", "N or M" -> range.
   Lower bounds (>=, >, at least, over, min., or more, +, minimum) and ~/approx/about/around/typical/+- -> unresolved (rows) / nothing (prose).
4. dell@4: a USB entry without Type-C/TB/USB4 or Type-A/USB-A keeps the literal list.
5. import.py: an explicit foreign sku/locator.sku vetoes before the textual SKU match. `_CAPNUM` reads "1,024GB" as 1024 (_caps, _strip_caps, neutral_name).
6. aoc_monitors@2: native refresh only from an explicit "N Hz Native" row.

Checks: bare `import.py --strict-parsers` rc 0 (parser_drift 0) and `build.py` rc 0, both under flock. Every tests/test_*.py module passes on its own.
New fixtures (review counterexamples): tests/test_review9.py, 18 tests.
Shared-file changes: scripts/import.py (naming helpers), scripts/docspec_r7tv.py, crawler/adapters/{_docspec_tvports,pb_pps_r7,anker_powerbanks,_powerstation,
shopify_powerstations,ankersolix_stations,dell,aoc_monitors}.py, data/decisions/policies.yaml, policy-lock.jsonl (written by the build), docs/index.html (build stamp).
Test pins updated: test_r7, test_r6, test_a2_r6_dell, test_review3, test_r7_powerbank_pps, test_a2_r8_aoc (plain-row native is no longer expected).
Open: Dell charge_port=dedicated is lost on the 5 platforms, because the whole structured result is dropped. A per-key fallback would need an A1 ruling.
