#!/usr/bin/env python3
"""KUXIU US store charger adapter (contract ARCHITECTURE 15.5), category chargers, r11 (A2-chg). Own module so the audited
shopify_chargers fingerprints (claim/mfr-chargers-structured@4) do not move; discover/fetch are the shared shopify_chargers._ShopC ones.

KUXIU (kuxiu.com; robots allow /products, terms have no automated-access clause) titles chargers '... GaN Power Adapter' /
'... Universal Travel Adapter'; the page prints a 'Model' row (RY-C40C-C, OL-H02-PD45). Products whose every variant SKU names a
non-US plug (45W-AU-Orange, 45W-mini-EU-Orange) are other-market listings; plug-adapter sets ('+ EU & UK Plug Adapter Set') are
bundles; a port '+' (USB-C + USB-A, 1C + 1A) is a port layout, not a bundle. The power banks on the same store stay in
shopify_powerbanks2 (kuxiu-us-powerbanks).

parse : spec values are bullet lines ('- 5V⎓3A ...', '- USB C1/C2 Output: ...'): the bullet is dropped so port names are read.
        'AVS: 9V-15V⎓2.67A' lines are USB PD AVS (Adjustable Voltage Supply), not PPS: they are dropped so a range is never read as PPS.
        v2 (review-11): the AVS exclusion is text-level, not layout-dependent: an AVS label cell (th/td/dt/li/div/span) with its value
        cell, and any inline 'AVS[:] <figure>' run up to the next tag, line, ';', '|' or PPS mention, wherever it sits ('USB-C: PD 3.0,
        AVS 9V-15V⎓2.67A', '<td>AVS</td><td>9-15V</td>'). Then the shared _charger.parse_store().
"""
import gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _charger as G
import _run
import shopify_chargers as SC

VERSION = 2
PORTPLUS = re.compile(r"\b\d?\s*[x×]?\s*(?:USB[- ]?|Type[- ]?)?[AC]\d?\s*\+\s*\d?\s*[x×]?\s*(?:USB[- ]?|Type[- ]?)?[AC]\d?\b", re.I)
KCHG = re.compile(r"charger|(?:power|travel|gan|wall) adapter", re.I)
KNOT = re.compile(r"plug adapter set|smart connector|ipad|power ?bank|wireless|magsafe|\bqi2?\b|\bstand\b|\bcase\b", re.I)
MODEL = re.compile(r"^([A-Z]{1,3}-[A-Z0-9]{2,10}(?:-[A-Z0-9]{1,6}){0,2})(?![A-Z0-9-])")


AVS_CELL = re.compile(r"(?is)<(t[hd]|dt|li|div|span|strong|b|p)\b[^>]*>\s*(?:(?:SPR|EPR|PD(?:\s*3\.\d)?)\s+)?AVS\s*[:：]?\s*</\1>\s*"
                      r"<(t[hd]|dd|li|div|span|p)\b[^>]*>\s*(?:<[^>]+>\s*)*\(?\s*(?:up to\s*)?\d.*?</\2>")
AVS_RUN = re.compile(r"(?i)\b(?:(?:SPR|EPR)\s+)?AVS\b\s*[:：]?\s*(?=\(?\s*(?:up to\s*)?\d)(?:(?!\bPPS\b)[^<\n;|])*")     # 'AVS' + a figure; the bare protocol name stays


def drop_avs(h):
    """USB PD AVS ranges are never PPS (review-11: text-level, any layout)."""
    return AVS_RUN.sub("", AVS_CELL.sub("", h or ""))


class KuxiuChargers(SC._ShopC):
    id, source_id, base, brand, brand_name = "kuxiu_chargers", "kuxiu-us-chargers", "https://kuxiu.com", "kuxiu", "KUXIU"
    version = VERSION

    def keep(self, p):
        t = p.get("title") or ""
        skus = [(v.get("sku") or "").upper() for v in p.get("variants") or []]
        if not KCHG.search(t) or KNOT.search(t) or SC.NON_US.search(t) or re.search(r"\+", PORTPLUS.sub(" ", t)):
            return False
        if re.search(r"(?i)\bcables?\b", t) and not re.search(r"(?i)(?:built-in|retractable) (?:\w+ )?cable", t):
            return False          # a cable-only listing; an adapter with its own built-in retractable cable is one charger model
        return not skus or not all(re.search(r"(?:^|-)(?:EU|UK|AU|JP|KR)(?:-|$)", s) for s in skus if s)

    def model_of(self, rows, skus, title, handle):
        p = SC._row(rows, "Model", "Product Model", "Model Number")
        if p and (m := MODEL.match(p.strip().upper())):
            return m[1], "printed Model row"
        return None, "no Model row"

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))

        def unbullet(h):
            h = re.sub(r"(>|<br\s*/?>|\n)(\s*)[-–•]\s+(?=[A-Za-z0-9])", r"\1\2", h or "")
            return drop_avs(h)
        prod = dict(d.get("product") or {})
        prod["body_html"] = unbullet(prod.get("body_html"))
        return G.parse_store(self, snap, unbullet(d["page"]), prod)


ALL = (KuxiuChargers,)

if __name__ == "__main__":
    which = {c.source_id: c for c in ALL}
    src = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in which else None
    if not src:
        raise SystemExit("usage: kuxiu_chargers.py <source-id> discover|fetch|parse  (" + ", ".join(which) + ")")
    _run.main(which[src]())
