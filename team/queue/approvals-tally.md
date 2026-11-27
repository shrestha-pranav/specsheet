# Coordinator approvals tally (owner review later)
Delegation: owner 2026-11-26 "Consider all policies approved, just keep a running tally so I can review them later."
Approvals under delegation carry `by: coordinator-delegated`. Grep policies.yaml for that string to list them all.
Still held (licensing-driven, not a data gap): claim/mfr-monitor-aoc@3 (www.aoc.com free:false, storage clause) — parked owner decision (b).

| date | policy | what it publishes | source agent / report |
|---|---|---|---|
| 2026-11-26 | claim/mfr-monitor-structured@12 | ASUS native refresh (overview-gated), LG O/C split, Lenovo max fix | A2-ref r10 |
| 2026-11-26 | claim/mfr-monitor-benq@5 | BenQ res.native + refresh_native | A2-ref r10 |
| 2026-11-26 | claim/mfr-monitor-dell@3 | Dell flk.pwm none from TÜV Flicker Free footnote | A2-ref r10 |
| 2026-11-26 | claim/derive-tuv-eye-comfort-5star@6 | re-pin only (lenovo_monitors@7) | A2-ref r10 |
| 2026-11-26 | rel/source-stated-hierarchy@17 | re-pin only | A2-ref r10 |
| 2026-11-26 | claim/document-power-pdo@5 | PDO from documents; IEC PS-class lines skipped; Belkin leaflets | A2-pb r10 |
| 2026-11-26 | claim/spec-image-power-pdo@3 | re-pin (docparse) | A2-pb r10 |
| 2026-11-26 | claim/hub-document-power-pdo@3 | re-pin (docparse) | A2-pb r10 |
| 2026-11-26 | claim/mfr-power-banks-structured@10 | pb_pps_r7@8 negation + exact model | A3-fix review-10 |
| 2026-11-26 | claim/derive-samsung-sfc2-pps@3 | SFC 2.0 => pd.pps, negation-safe | A3-fix review-10 |
| 2026-11-26 | claim/mfr-power-stations-structured@10 | UPS alternatives/lower bounds never exact | A3-fix review-10 |
| 2026-11-26 | claim/document-tv-ports@3 | TV port inventory only from trusted hdmi.count | A3-fix review-10 |
| 2026-11-26 | rel/bundle-contents@10 | re-pin (pb parsers) | A3-fix review-10 |

## Source-policy rulings under delegation (owner review)
| date | policy version | ruling |
|---|---|---|
| 2026-11-26 | 2026-11-26.8 | www.lg.com crawl human_only (terms bar manual/automated scraping); ~1,414 stored values stay published (parked a) |
| 2026-11-26 | 2026-11-26.10 | Terms audit r11 (team/queue/terms-audit-r11.yaml, apply-terms-audit.py): 24 hosts human_only on A/R/X basis incl. www.asus.com (10,841 values), rog.asus.com (3,651), www.tp-link.com (3,927), us.tcl.com (2,088), www.cyberpowersystems.com (4,929), assets.tripplite.com (4,898), www.kingston.com (425), NETGEAR x3 (661), Winix (307), Levoit (64); stored values stay published (parked a) |
| 2026-11-26 | 2026-11-26.10 | DEFERRED LICENSING (basis B, personal non-commercial licence, no automated-access clause; crawl stays agent): www.sandisk.com 2,605, www.vizio.com 1,922, www.dell.com 1,418, www.dreametech.com 542, www.gl-inet.com 508, us.mova.tech 265, documents.sandisk.com 124, www.irobot.com 119, learn.microsoft.com 18, www.microsoft.com, www.razer.com. Inconsistency to note: earlier B-basis flips (www.se.com/www.apc.com .2, satechi .9) predate the 'licensing later' direction and were left as human_only |
| 2026-11-26 | claim/appliances-energystar@2 | see report | r11 |
| 2026-11-26 | claim/appliances-es-pattern@2 | see report | r11 |
| 2026-11-26 | claim/mfr-power-banks-nitecore@1 | see report | r11 |
| 2026-11-26 | claim/mfr-power-stations-pecron@1 | see report | r11 |
| 2026-11-26 | claim/mfr-chargers-kuxiu@1 | see report | r11 |
| 2026-11-26 | claim/mfr-laptop-ports@4 | see report | r11 |
| 2026-11-26 | rel/appliances-es-pattern-coverage@2 | see report | r11 |
| 2026-11-26 | rel/source-stated-hierarchy@18 | see report | r11 |
| 2026-11-27 | claim/smart-home-zigbee2mqtt@2 | see report | r12 |
| 2026-11-27 | claim/cpsc-recalls@1 | see report | r12 |
| 2026-11-27 | claim/light-bulbs-energystar@1 | see report | r12 |
| 2026-11-27 | claim/appliances-siblings-energystar@1 | see report | r12 |
| 2026-11-27 | claim/appliances-siblings-es-pattern@1 | see report | r12 |
| 2026-11-27 | claim/mfr-power-banks-nitecore@2 | see report | r12 |
| 2026-11-27 | claim/mfr-power-stations-pecron@2 | see report | r12 |
| 2026-11-27 | claim/mfr-chargers-kuxiu@2 | see report | r12 |
| 2026-11-27 | claim/usbif-certified-products@1 | see report | r12 |
