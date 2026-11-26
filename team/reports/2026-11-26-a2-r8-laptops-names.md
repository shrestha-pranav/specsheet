# A2-lap r8 2026-11-26: laptop per-port facts beyond Lenovo + SSD variant labels
**Decisions first.** No fetches: every fact comes from stored snapshots. Bare `import.py --strict-parsers` rc 0, parser_drift 0; `build.py` rc 0 (both run under flock).
New and reissued policies are `approval: pending`. Each superseded version is in retired_policies verbatim with a `retired:` line.
- **HP / Acer: nothing done.** Neither has raw snapshots. manufacturers.yaml records hp.com (Akamai) and acer.com as blocked. Domains needed (for A2-mon / coordinator, not probed): HP QuickSpecs `www8.hp.com/h20195` and `support.hp.com/us-en`; Acer `www.acer.com/us-en` and `store.acer.com`. Both are owned by sites that are already blocked, so a ruling is needed before anyone tries them.
- New pure parser `crawler/adapters/_xports.py` uses the _lports per-port model (asus / dell / surface readers). A fact comes only from the port group that prints it, never pooled. A bare "power delivery" gives no W and no charge port. "support display" is not DisplayPort. Hedges ("Up to 2x" USB-C, OR, "(optional)", "only for computers with", "AMD Ryzen 200 Series:"), unknown lines, and Surface size sections that disagree all keep the old literal claim.
- Judgement call to review: a Dell line with no Type-C/TB/USB4 wording ("1 USB 3.2 Gen 1 (5 Gbps) port") is read as non-USB-C, because Dell names every Type-C port explicitly.

## Fill (claim diff old vs new parser over every stored page; identifiers and aliases are identical)
| source | structured port.usbc_list | tb_usb4 | video_out | charge_port | literal kept |
|---|---|---|---|---|---|
| asus-us (142 pages) | 334 | 271 | 167 | 0 (DC-in shape and PD direction are never printed) | 25 (Type-A-only Chromebooks, hedged USB-C) |
| dell-us (100) | 78 | 49 | 64 | 0 (the barrel pages are all platform-conditional) | 21 |
| microsoft-surface (15) | 8 | 5 | 1 | 4 usb-c (Surface Connect + USB-C = nothing) | 0 |

## Item 2: SSD names (sandisk_ssd@7, samsung_ssd@4; claims byte-identical, title aliases gain `sku`)
87 of 324 SSD configuration names changed; duplicate names went from 102 to 28. Examples: My Passport "- Gold" on every colour -> "- 1TB - Blue" / "- 500GB - Red";
SN850X XHE "without Heatsink" -> "with Heatsink"; GX PRO 8100/850X TAN -> "without Heatsink - 2TB"; SN7100S/SN5100S 2230 SKUs no longer say "M.2 2280";
Extreme Portable V3 G25B -> "..., Monterey Blue - 1TB"; Samsung MU-PG2T0B/AM "T9 1 TB" -> "...2TB (Black)"; MZ-V9P2T0GW drops its wrong "1 TB" (Samsung's Capacity row says 1TB, its title says 2TB).
import.py: new `_strip_caps()` and `bound_label()`; `own_alias()` now prefers the configuration's own bound label.
Left as is: TEAMGROUP C128/C129 and Kingston SNV3S/SNV3SM3, because no per-SKU label is stated. Where SanDisk prints one Model Number under several descriptors, only the shared words are kept ("...NVMe SSD, M.2").

## Policies (pending)
- claim/asus-techspec-typed@3 -> @4: asus@3. Widens asus-us with port.usbc_list, port.tb_usb4, port.video_out.
- claim/mfr-laptop-ports@1 (NEW): dell@2 and surface@2. Port keys only (dell-us and microsoft-surface had no claim policy before).
- claim/mfr-ssd-structured@7 -> @8 (sandisk_ssd@7) and claim/mfr-ssd-samsung@3 -> @4 (samsung_ssd@4): no widening.
- Fingerprint re-pins only: claim/mfr-ssd-sandisk-datasheet@3 -> @4 (it imports sandisk_ssd); claim/mfr-routers-structured@3 -> @4 and claim/mfr-routers-class@3 -> @4 (asus_routers imports asus; its output diff over 82 pages is 0).
- rel/source-stated-hierarchy@11 -> @12: pins asus@3, dell@2, surface@2, sandisk_ssd@7, samsung_ssd@4.

## Files
New: _xports.py, tests/test_a2_r8_laptop_ports.py (10), tests/test_a2_r8_names.py (8). Edited: asus.py v3, dell.py v2, surface.py v2, sandisk_ssd.py v7, samsung_ssd.py v4. Shared: scripts/import.py (naming only), policies.yaml (7 blocks + 7 retired), policy-lock.jsonl (build-written). Not mine: registry.py, source-policy.yaml.

## Open questions
1. My first import run (drift-failed) also locked A2-mon's claim/mfr-monitor-aoc@1. test_adversarial now fails only on A2-mon's unlocked claim/mfr-monitor-aoc@2, which is their in-flight work.
2. A2-mon may also need hierarchy pins. If so, stack them as @13 on top of my @12.
3. The ASUS "DC-in" / Dell "power-adapter port" connector shape is unstated, so charge_port stays empty. Should A1 add an enum value such as `dedicated`?
