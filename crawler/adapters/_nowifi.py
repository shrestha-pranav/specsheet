"""Wired-gateway rule shared by ubiquiti_routers and glinet_routers (coordinator ruling 2, 2026-11-24 r2). Kept out of _router.py so the
TP-Link / NETGEAR / ASUS parser fingerprints (which hash _router.py) do not change for a rule they never use."""
import re

import _contract as C
from _router import NEG

WIFI_KEYS = ("wifi.generation", "wifi.band_count", "wifi.has_6ghz", "wifi.rate_24_mbps", "wifi.rate_5_mbps", "wifi.rate_6_mbps")
WIFI_WORDS = re.compile(r"wi-?\s?fi|802\.11|wireless|\bwlan\b|\bssid|(?<![\d.])(?:2\.4|5|6)\s*GHz\b|antenna", re.I)


def add_no_wifi(pr, adapter, snap, raw, loc_kind, loc_val, label):
    """Coordinator ruling 2 (2026-11-24 r2): a wired gateway whose maker spec enumerates its complete interface set and no Wi-Fi radio.
    The Wi-Fi keys become not_applicable with basis=complete_enumeration and the enumeration kept as raw. Callers decide completeness;
    silence alone never reaches here."""
    raw = raw if isinstance(raw, str) else " | ".join(raw)
    for k in WIFI_KEYS:
        pr.claims.append(C.claim(loc_val, k, None, None, raw, "s1", adapter, "adapter", snap.fetched_at,
                                 locator={loc_kind: loc_val, "label": label}, conditions=dict(NEG), status="not_applicable"))
