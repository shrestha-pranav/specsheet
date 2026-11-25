"""Monitor USB-C facts the makers print, shared by lenovo_monitors@5 and asus_monitors@3 (A2-keys 2026-11-25). Pure.

usb.usbc_alt_dp (text): the DisplayPort-over-USB-C statement of the monitor's USB-C video INPUT port, per port line. A line counts only
  when _monports.classify() calls it an input (USB-C/TB/USB4, not downstream/out/data-only) AND the line itself names DisplayPort / DP /
  Alt Mode. Value = 'DP <ver> Alt Mode' / 'DP Alt Mode' / 'DP <ver>' as printed (TM/R marks dropped). Lines that state different
  versions -> nothing (per-port facts are never pooled); a Thunderbolt input that prints no DP -> not counted (never inferred).
usb.kvm (bool): affirmative from the maker's own feature row: Lenovo PSREF Special Features item 'KVM Switch' / 'KVM Switch (with eKVM)',
  ASUS 'KVM Switch : Yes' or a port row '(For KVM Switch)'. False only from the maker's explicit 'KVM Switch : No'. Never from absence.
"""
import re

import _monports as MP

DPV = re.compile(r"(?:DisplayPort|\bDP)\W{0,3}\s*(\d\.\d[a-z]?)?", re.I)
ALT = re.compile(r"alt\.?\s*mode", re.I)


def alt_dp_line(line):
    """One port line -> 'DP 1.4 Alt Mode' etc., or None when the line is not a USB-C video input or names no DisplayPort."""
    if MP.classify(line) != "input":
        return None
    m = DPV.search(line)
    if not m:
        return None
    v = "DP" + (f" {m.group(1)}" if m.group(1) else "")
    return v + (" Alt Mode" if ALT.search(line) else "")


def alt_dp(lines):
    """-> (value, the port line that states it) or (None, None). Two USB-C inputs stating different DP versions -> nothing."""
    hits = {}
    for l in lines:
        v = alt_dp_line(l)
        if v:
            hits.setdefault(v, l)
    if len(hits) != 1:
        return None, None
    (v, l), = hits.items()
    return v, l


KVM_ITEM = re.compile(r"^\s*KVM Switch\b", re.I)


def kvm_lenovo(items):
    """Lenovo Special Features items -> (True, item) when one is a 'KVM Switch' feature, else (None, None)."""
    for x in items:
        for part in re.split(r"\^\|\^| \| |\n", x):
            if KVM_ITEM.match(part):
                return True, part.strip()
    return None, None


def kvm_asus(F):
    """ASUS spec rows {label: value} -> (bool, raw) from 'KVM Switch : Yes/No' or a '(For KVM Switch)' port row, else (None, None)."""
    v = (F.get("KVM Switch") or "").strip()
    if re.fullmatch(r"yes\b.*", v, re.I):
        return True, f"KVM Switch: {v}"
    if re.fullmatch(r"no", v, re.I):
        return False, f"KVM Switch: {v}"
    for k, val in F.items():
        if re.search(r"\(for KVM switch\)", val or "", re.I):
            return True, f"{k}: {val}"
    return None, None
