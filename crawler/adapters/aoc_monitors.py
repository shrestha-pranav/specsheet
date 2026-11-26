#!/usr/bin/env python3
"""AOC US monitor adapter v1 (contract ARCHITECTURE 15.5), category monitors (A2-mon r8, 2026-11-26). Source = www.aoc.com/us product pages.

robots   : https://www.aoc.com/robots.txt = 'User-Agent: * Allow: /' (2026-11-26). Terms (/us/legal-disclosure) have no automated-access
           clause but say 'Permanent storage, reproduction or distribution of the pages is prohibited': fetch() therefore stores ONLY the
           spec excerpt (title, schema.org JSON-LD, the specification accordion), never the full page (to_clear in data/source-policy.yaml).
discover : https://www.aoc.com/sitemap-en-us.xml -> /us/monitors/<slug> and /us/gaming/monitors/<slug> (category-* listing pages skipped).
fetch    : the product page (~0.3 MB SSR), 1 req/s, crawler UA; a 403/429 stops the run (no workaround).
parse    : pure. Spec accordion = groups (accordion title h3) of product-specification label/value rows. One page = one model:
           mfr_model = the schema.org Product 'model' (Q27G40SDE) and it must equal the URL slug (case-insensitive), else the page is
           skipped (22B30H3's <title> says 24B3HM: the title is never used for identity). The JSON-LD name is the marketing alias.
Traps    : the only refresh row is 'Max Refresh rate'. res.refresh_max = its figure, unless a higher Hz figure appears elsewhere on the page
           (24G51F row 144 Hz, copy '144Hz/OC 180Hz': the row is then the native rate and neither key is written). res.refresh_native = the explicit 'N Hz Native'
           figure when the row says OC ('260Hz (OC, 240Hz Native)'); otherwise the single plain 'N Hz' figure only when nothing on the page
           (rows, title, JSON-LD description) says OC/overclock/dual mode and no Hz figure there is higher than N (outside the signal-
           frequency rows). flk.pwm 'none' ONLY from the maker's 'Flicker-Free' row naming Flicker Free / Yes; Anti Blue Light, silence
           and 'No' write nothing. Counts: 'HDMI 2.1 x 2' style items of the HDMI / DisplayPort rows (an 'out' item is not counted; an
           item without a count writes nothing). usb.usbc_inputs only from the 'USB-C connectivity' row through _monports (ambiguous
           -> nothing; zero never written); usb.usbc_pd_w only from that row when it is a video input with one W figure.
"""
import gzip, html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _run
import _monports as MP
import _monusb as MU

ID, VERSION, SOURCE = "aoc_monitors", 1, "aoc-us-monitors"
CATEGORIES = {"monitors"}
ADAPTER = f"{ID}@{VERSION}"
SITEMAP = "https://www.aoc.com/sitemap-en-us.xml"
DELAY = 1.0
PROD = re.compile(r"<loc>\s*(https://www\.aoc\.com/us/(?:gaming/)?monitors/([a-z0-9][a-z0-9-]*))\s*</loc>")
ROW = re.compile(r'accordion__section-button-title"><h3[^>]*>(.*?)</h3>|product-specification__label"><span class="subtitle">(.*?)</span></div>'
                 r'<div class="product-specification__value">(.*?)</div></div>', re.S)
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def txt(s):
    s = re.sub(r"<[^>]+>", " | ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).replace("\xa0", " ").replace("™", "").replace("®", "").strip(" |").replace(" | | ", " | ")


def excerpt(h):
    """Full page -> the parts parse() reads (title, JSON-LD, spec accordion). Terms bar permanent storage of the pages."""
    parts = re.findall(r"<title>.*?</title>", h, re.S)[:1] + [m.group(0) for m in LD.finditer(h)]
    i, j = h.find("accordion__section-button-title"), h.rfind("product-specification__value")
    if i >= 0 and j > i:
        parts.append(h[max(0, h.rfind("<", 0, i)):h.find("</div></div>", j) + 12])
    return "\n".join(parts)


class AocMonitors:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap: {getattr(r, 'status_code', r)}", {})
        seen = {}
        for url, slug in PROD.findall(r.text):
            if not slug.startswith("category-"):
                seen.setdefault(slug, url)
        refs = [C.Ref(SOURCE, k, u, {}) for k, u in sorted(seen.items())]
        return C.Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            if st in (403, 429):
                raise _run.StopCrawl(f"{st} on {ref.url}: stop, no workaround")
            return s
        body = excerpt(r.content.decode("utf-8", "replace")).encode()
        s = C.Snapshot(self.store.put(gzip.compress(body, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def spec_rows(h):
    """-> [(group, label, [value items])] in page order. A value cell holds one or more <span> items."""
    out, grp = [], ""
    for m in ROW.finditer(h):
        if m[1] is not None:
            grp = txt(m[1])
        else:
            vals = [txt(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", m[3], re.S)] or [txt(m[3])]
            out.append((grp, txt(m[2]), [v for v in vals if v]))
    return out


def ld_product(h):
    for m in LD.finditer(h):
        try:
            d = json.loads(m[1])
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return {}


PANEL = [(r"(?i)^QD[- ]?OLED$", "QD-OLED"), (r"(?i)^W-?OLED$", "WOLED")]                 # 'Backlight type' row (OLED subtype)
PANEL_TYPE = [(r"(?i)^QD ?- ?OLED(?: \(\d+(?:st|nd|rd|th) Generation\))?$", "QD-OLED"), (r"(?i)^Fast IPS$", "Fast IPS"), (r"(?i)^Nano IPS$", "Nano IPS"),
              (r"(?i)^(?:IPS|IPS LCD|AH-?IPS|ADS)$", "IPS"), (r"(?i)^Fast VA(?: with Quantum Dot)?$", "Fast VA"), (r"(?i)^M?VA$", "VA"), (r"(?i)^TN$", "TN")]                                                       # bare 'OLED' / 'Nano IPS'-less pages: nothing
HZ = re.compile(r"(\d{2,4})\s*Hz\b", re.I)
OC = re.compile(r"\bOC\b|overclock|dual[- ]mode", re.I)
CNT = re.compile(r"(?:\bx\s*(\d)\b|^\s*(\d)\s*x\b)", re.I)
VESA = ("75x75", "100x100", "200x100", "200x200", "300x300", "400x400")


def item_count(v):
    """'HDMI 2.1 x 2' / 'Display port 1.4 (DSC) x1' / '2 x HDMI 2.0' -> 2/1/2; None when no count is printed."""
    m = CNT.search(v)
    return int(m[1] or m[2]) if m else None


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "AOC US product page " + snap.ref.key}]
    rows = spec_rows(h)
    by, grp = {}, {}
    for g, l, v in rows:
        by.setdefault(l, v); grp.setdefault(l, g)
    get = lambda l: " | ".join(by[l]) if by.get(l) else None
    ld = ld_product(h)
    model = str(ld.get("model") or "").strip().upper()
    if not rows or not re.fullmatch(r"[A-Z0-9]{4,14}", model):
        pr.absences.append({"key": "*", "reason": "no spec accordion / schema.org Product model (not a monitor spec page)", "source": "s1"})
        return pr
    if model != re.sub(r"[^A-Z0-9]", "", snap.ref.key.upper()):
        pr.absences.append({"key": "*", "reason": f"Product model {model!r} is not the page's URL slug {snap.ref.key!r}", "source": "s1"})
        return pr
    brand = (ld.get("brand") or {}).get("name") if isinstance(ld.get("brand"), dict) else None
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "aoc", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"], "series": "AGON" if brand and "AGON" in brand.upper() else None})
    name = re.sub(r"(?i)\s+monitor$", "", str(ld.get("name") or "")).strip()
    pr.aliases.append({"text": name or f"AOC {model}", "kind": "marketing_name"})

    def add(k, v, label, quote=None, kind=None, extra=None, conditions=None):
        if v in (None, "", []):
            return
        raw = f"{label}: {get(label)}" if label in by else label
        c = C.claim(model, k, v, None, raw, "s1", ADAPTER, "adapter", snap.fetched_at,
                    locator=dict({"model_code": model, "label": f"{grp.get(label) or 'Specifications'} > {label}"}, **(extra or {})),
                    quote=quote or raw, conditions=conditions)
        if kind:
            c["kind"] = kind
        pr.claims.append(c)

    # ---- size / panel / resolution -------------------------------------------------------------------------------------------------
    if (sz := get("Screen size (inch)")) and (m := re.fullmatch(r"\s*(\d{2}(?:\.\d{1,2})?)\s*(?:\"|inch(?:es)?)?\s*", sz)):
        d = float(m[1])
        add("gen.viewable_diag", int(d) if d == int(d) else d, "Screen size (inch)")
        if d == int(d):
            add("gen.size_class", int(d), "Screen size (inch)")
        else:
            add("gen.size_class", MP.size_class(m[1]), "Screen size (inch)", kind="derived", extra={"derivation": MP.DERIVATION})
    bl, pt = get("Backlight type"), get("Panel type")
    tech = next((v for rx, v in PANEL if bl and re.fullmatch(rx, bl.strip())), None) if pt and re.fullmatch(r"(?i)\s*OLED\s*", pt) else None
    if tech:
        add("panel.technology", tech, "Backlight type", quote=f"Panel type: {pt} | Backlight type: {bl}")
    elif pt and (hit := next((v for rx, v in PANEL_TYPE if re.fullmatch(rx, pt.strip())), None)):
        add("panel.technology", hit, "Panel type")
    w = hgt = None
    if (r := get("Panel resolution")) and (m := re.fullmatch(r"\s*(\d{3,4})\s*[x×*]\s*(\d{3,4})\s*", r)):
        w, hgt = int(m[1]), int(m[2])
        add("res.native", f"{w}x{hgt}", "Panel resolution"); add("res.width_px", w, "Panel resolution"); add("res.height_px", hgt, "Panel resolution")
    # ---- refresh ---------------------------------------------------------------------------------------------------------------------
    mr = get("Max Refresh rate")
    if mr:
        exp = re.fullmatch(r"\s*(\d{2,4})\s*Hz\s*\(\s*OC\s*,\s*(?:(\d{2,4})\s*Hz\s+Native|Native\s+(\d{2,4})\s*Hz)\s*\)\s*", mr, re.I)
        plain = re.fullmatch(r"\s*(\d{2,4})\s*Hz\s*", mr, re.I)
        oc_only = re.fullmatch(r"\s*(\d{2,4})\s*Hz\s*OC\s*", mr, re.I)
        nat = exp and int(exp[2] or exp[3])
        if exp and nat < int(exp[1]):
            add("res.refresh_max", int(exp[1]), "Max Refresh rate")
            add("res.refresh_native", nat, "Max Refresh rate")
        elif oc_only:
            add("res.refresh_max", int(oc_only[1]), "Max Refresh rate")          # '180Hz OC': the native rate is not printed
        elif plain:
            n = int(plain[1])
            other = [(l, " | ".join(v)) for _, l, v in rows if not re.search(r"(?i)signal frequency|frequency", l)]
            ctx = [x for _, x in other] + [re.sub(r"<[^>]+>", " ", t) for t in re.findall(r"<title>(.*?)</title>", h, re.S)[:1]] \
                + [str(ld.get("description") or ""), str(ld.get("name") or "")]
            higher = any(int(z) > n for x in ctx for z in HZ.findall(x))
            if not higher:     # 24G51F: row 'Max Refresh rate 144 Hz', copy '144Hz/OC 180Hz' -> the row is the native rate, the max is not in it
                add("res.refresh_max", n, "Max Refresh rate")
            if not any(OC.search(x) for x in ctx) and not higher:
                add("res.refresh_native", n, "Max Refresh rate", quote=f"Max Refresh rate: {mr} (no OC / overclock / dual-mode statement and no higher "
                                                                        f"rate anywhere on the page)")
    # ---- flicker ---------------------------------------------------------------------------------------------------------------------
    ff = get("Flicker-Free") or get("Flicker Free")
    if ff and re.fullmatch(r"(?i)\s*(?:(?:TUV\s+)?flicker[- ]?free|yes)\s*", ff):
        add("flk.pwm", "none", "Flicker-Free" if "Flicker-Free" in by else "Flicker Free")
    # ---- video inputs ----------------------------------------------------------------------------------------------------------------
    def counted(label, rx, version_rx):
        its = by.get(label) or []
        its = [i for x in its for i in re.split(r"\s*[,;+/]\s*(?=(?:\d\s*x\s*)?" + rx + ")", x, flags=re.I)]     # 'HDMI 2.0 x 1, HDMI 1.4 x 1'
        its = [i for i in its if re.search(rx, i, re.I)]
        if not its or any(re.search(r"(?i)\bout(put)?\b|daisy|\bMST\b", i) for i in its):
            return None, None, its
        ns = [item_count(i) for i in its]
        if None in ns:
            return None, None, its
        vs = {m[1] for i in its if (m := re.search(version_rx, i, re.I))}
        return sum(ns), (vs.pop() if len(vs) == 1 else None), its
    n, v, _ = counted("HDMI", r"HDMI", r"HDMI\s*(\d\.\d)")
    add("vin.hdmi_count", n, "HDMI")
    add("vin.hdmi_version", v, "HDMI")
    n, _, _ = counted("DisplayPort", r"(?:Display\s?port|DP\b)", r"(?:Display\s?port|DP)\s*(\d\.\d)")
    add("vin.dp_count", n, "DisplayPort")
    # ---- USB-C -------------------------------------------------------------------------------------------------------------------------
    uc = by.get("USB-C connectivity") or []
    if uc:
        n_in, _ = MP.count_inputs(uc)
        if n_in:
            add("usb.usbc_inputs", n_in, "USB-C connectivity")
            alt, aline = MU.alt_dp(uc)
            if alt:
                add("usb.usbc_alt_dp", alt, "USB-C connectivity", quote=f"USB-C connectivity: {aline}")
            ws = {int(x) for l in uc if MP.classify(l) == "input" for x in re.findall(r"(\d{2,3})\s*W\b", l)}
            if len(ws) == 1:
                add("usb.usbc_pd_w", ws.pop(), "USB-C connectivity")
    if (k := get("KVM")) and re.search(r"(?i)type[- ]?c|type[- ]?b|\byes\b|usb", k) and not re.fullmatch(r"(?i)\s*no\s*", k):
        add("usb.kvm", True, "KVM")
    if (vs := get("Vesa wallmount")) and (m := re.fullmatch(r"\s*(\d{2,3})\s*[x×*]\s*(\d{2,3})\s*(?:mm)?\s*", vs)) and f"{m[1]}x{m[2]}" in VESA:
        add("ergo.vesa", f"{m[1]}x{m[2]}", "Vesa wallmount")
    if (pm := get("Power consumption on (maximum) in watts")) and (m := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:W)?\s*", pm)):
        add("pwr.max", int(float(m[1])) if float(m[1]) == int(float(m[1])) else float(m[1]), "Power consumption on (maximum) in watts")
    pr.fingerprints = {"raw": snap.snapshot, "labels": [f"{g} > {l}" for g, l, _ in rows][:300]}
    return pr


if __name__ == "__main__":
    _run.main(AocMonitors())
