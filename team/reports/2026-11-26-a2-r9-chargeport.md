# A2-lap2 r9 2026-11-26: port.charge_port `dedicated`
**Decisions first.** No fetches; stored snapshots only. All new/reissued policies are `approval: pending`; superseded versions are in retired_policies verbatim with `retired:`.
- `dedicated` = the maker's own port list names a DC-in / power-adapter port / power connector of unstated shape. Never emitted from absence of USB-C charging. A stated shape stays specific (barrel, proprietary).
- _xports.py (asus "DC-in", dell "power-adapter port"/"power jack"): unknown-shape power port now gives `dedicated` (was: nothing, and it blocked usb-c). Dedicated/barrel + a USB-C segment that itself states charging -> list `["dedicated","usb-c"]` (was: nothing). Zero such cells in stored data.
- _lports.py (Lenovo): a "power connector" / "DC-in" without slim/round tip -> `dedicated`. No stored PSREF cell has one, so Lenovo claims are byte-identical. Lenovo's existing rule (connector wins; USB-C PD input ignored when a connector is named) is NOT changed to a list: that would rewrite ~740 claims; A1 to rule if wanted.
- Surface: no change in output (4 usb-c kept); Surface Connect + USB-C charging in separate segments would now be a list.
- Profile enum in spec-profile.yaml is open (no value list) and was not edited (A1 owns it): label/example still say barrel/MagSafe/USB-C.

## Fill (port.charge_port claims, scratch import then real import)
| source | before | after |
|---|---|---|
| asus-us | 0 | 25 dedicated |
| dell-us | 0 | 11 dedicated |
| lenovo-psref | 1863 (351 barrel / 390 proprietary / 1122 usb-c) | 1863 identical |
| microsoft-surface | 4 usb-c | 4 usb-c |

## Policies (pending)
- claim/asus-techspec-typed@4 -> @5 (asus@4; widens asus-us with port.charge_port).
- claim/mfr-laptop-ports@1 -> @2 (dell@3, surface@3; no widening). claim/mfr-structured-datasheet@4 -> @5 (lenovo_psref@5; no widening).
- Fingerprint re-pins only: claim/mfr-routers-structured@4 -> @5, claim/mfr-routers-class@4 -> @5 (asus_routers imports asus); claim/mfr-monitor-structured@9 -> @10 and claim/derive-tuv-eye-comfort-5star@3 -> @4 (lenovo_monitors imports lenovo_psref: drift found by the first strict run).
- rel/source-stated-hierarchy@12 -> @13 -> @14: @13 was locked by my first import before the lenovo_monitors drift appeared, never approved, so it is retired and @14 carries all pins (lenovo_psref@5, asus@4, dell@3, surface@3, lenovo_monitors@6 new fingerprint).

## Files
Edited: _lports.py, _xports.py, asus.py v4, dell.py v3, surface.py v3, lenovo_psref.py v5 (version numbers only), tests/test_a2_r8_laptop_ports.py (one assertion: power-adapter port now dedicated), data/decisions/policies.yaml, policy-lock.jsonl (import-written). New: tests/test_a2_r9_chargeport.py (6). Shared scripts untouched.

## Open questions
1. Lenovo connector + USB-C PD input: keep scalar (connector only) or emit list like _xports? 2. Add `dedicated` to the profile enum / relabel (A1).
