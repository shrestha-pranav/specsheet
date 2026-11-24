#!/usr/bin/env python3
"""BenQ US monitor adapter v1 (contract ARCHITECTURE 15.5), category monitors. Source = www.benq.com/en-us/monitor/<line>/<model>/spec.html.

discover : https://www.benq.com/en-us/sitemap.xml (one request; robots allows /en-us/ except search pages) -> every /en-us/monitor/<line>/<slug>/spec.html
           except the accessory/ and software/ lines (stands, hoods, pucks, apps).
fetch    : the spec page (server-rendered AEM, ~370 KB), stored gzip. 1 req/s.
parse    : pure. 'spec-container' blocks = a category ('Display', 'Connectivity', 'Eye Care', ...) + <li class="item"> name/detail pairs. One page =
           one model; mfr_model = the local-navigation title (EX2710S). A page whose model selector names more than one model is skipped (absence).
Traps    : flk.pwm is written ONLY from an affirmative 'Flicker-free Technology: Yes' row (stored as the maker's declaration 'none', the literal quoted:
           TUV flicker-free may be tested at default brightness only). 'No', a blank or silence writes nothing. usb.usbc_pd_w only from a row that
           names USB-C (or Thunderbolt) power delivery with a single wattage; two figures (e.g. 'up to 90W / 65W') write nothing. Refresh 'Refresh
           Rate (Hz)' may carry several modes ('165 (DP), 144 (HDMI)'): the maximum stated is res.refresh_max. Panel 'IPS'/'VA'/'TN'/'OLED' only.
"""
import gzip, html, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _run

ID, VERSION, SOURCE = "benq_monitors", 1, "benq-us-monitors"
CATEGORIES = {"monitors"}
ADAPTER = f"{ID}@{VERSION}"
SITEMAP = "https://www.benq.com/en-us/sitemap.xml"
DELAY = 1.0
LOC = re.compile(r"<loc>(https://www\.benq\.com/en-us/monitor/([a-z0-9-]+)/([a-z0-9-]+)/spec\.html)</loc>")
SKIP_LINES = {"accessory", "software"}
CONT = re.compile(r'<div class="spec-container">(.*?)(?=<div class="spec-container">|<div class="g6-|\Z)', re.S)
ITEM = re.compile(r'<li class="item">\s*<div class="name">(.*?)</div>\s*<div class="detail">(.*?)</div>', re.S)


def txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


class BenqMonitors:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        seen = {}
        for url, line, slug in LOC.findall(r.text):
            if line not in SKIP_LINES:
                seen.setdefault(slug, {"url": url, "line": line})
        refs = [C.Ref(SOURCE, s, d["url"], {"line": d["line"]}) for s, d in sorted(seen.items())]
        return C.Discovery(refs, True, None, {"models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def spec_rows(h):
    """-> list of (category, name, detail) in page order."""
    out = []
    for blk in CONT.findall(h):
        cat = re.search(r'<p class="category">(.*?)</p>', blk, re.S)
        for n, d in ITEM.findall(blk):
            out.append((txt(cat[1]) if cat else "", txt(n), txt(d)))
    return out


def parse_html(snap, h):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "BenQ US spec page " + snap.ref.key}]
    rows = spec_rows(h)
    t = re.search(r"localNavigation\.type = g6-product-spec-page</p>.*?<p>\s*([^<]+?)\s*</p>", h, re.S)
    if not rows or not t:
        pr.absences.append({"key": "*", "reason": "no spec rows / model title (not a spec page)", "source": "s1"})
        return pr
    model = txt(t[1]).upper()
    if not re.fullmatch(r"[A-Z]{1,4}\d{2,4}[A-Z0-9-]*", model):
        pr.absences.append({"key": "*", "reason": f"title {model!r} is not one model code", "source": "s1"})
        return pr
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "benq", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"], "series": snap.ref.hints.get("line")})
    pr.aliases.append({"text": f"BenQ {model}", "kind": "marketing_name"})
    by = {}
    for cat, n, d in rows:
        by.setdefault(n, (cat, d))

    def add(k, v, label, quote=None):
        if v in (None, "", []):
            return
        cat, d = by[label]
        pr.claims.append(C.claim(model, k, v, None, f"{label}: {d}", "s1", ADAPTER, "adapter", snap.fetched_at,
                                 locator={"model_code": model, "label": f"{cat} > {label}"}, quote=quote))

    def get(label):
        return by.get(label, (None, None))[1]

    for lab in ("Flicker-free Technology", "Flicker-Free Technology", "Flicker-free"):
        v = get(lab)
        if v is not None and re.fullmatch(r"(?i)yes", v.strip()):
            add("flk.pwm", "none", lab, quote=f"{lab}: {v}")
            break
    tuv = get("TUV Certificate")
    if tuv and tuv.strip().lower() not in ("no", "-", "n/a"):
        add("flk.cert", ["TUV " + x.strip() for x in re.split(r"[,/]", tuv) if x.strip()], "TUV Certificate", quote=f"TUV Certificate: {tuv}")
    pt = get("Panel Type")
    if pt:
        m = re.fullmatch(r"\s*(IPS|VA|TN|QD-OLED|WOLED)\s*", pt, re.I)
        if m:
            add("panel.technology", m[1].upper(), "Panel Type")
    rr = get("Refresh Rate (Hz)") or get("Refresh Rate")
    if rr:
        nums = [int(x) for x in re.findall(r"(?<![\d.])(\d{2,3})(?![\d.])", rr)]
        if nums:
            add("res.refresh_max", max(nums), "Refresh Rate (Hz)" if get("Refresh Rate (Hz)") else "Refresh Rate")
    res = get("Resolution (max.)") or get("Resolution")
    if res and (m := re.fullmatch(r"\s*(\d{3,4})\s*[x×]\s*(\d{3,4})\b.*", res)):
        lab = "Resolution (max.)" if get("Resolution (max.)") else "Resolution"
        add("res.width_px", int(m[1]), lab); add("res.height_px", int(m[2]), lab)
    sz = get("Screen Size")
    if sz and (m := re.fullmatch(r"\s*(\d{2}(?:\.\d)?)\s*(?:inch|\")\s*", sz)):
        add("gen.size_class", float(m[1]) if "." in m[1] else int(m[1]), "Screen Size")
    # USB-C power delivery: (a) the 'Power Delivery(USB C / Thunderbolt )' row with ONE figure ('90', '90W'); (b) an upstream port label
    # 'USB C(PowerDelivery 65W, DisplayPort Alt Mode, Data)'. Downstream 'power charging 7.5W' never counts; two different figures write nothing.
    ws = {}
    for _, n, d in rows:
        if re.match(r"Power Delivery\s*\(USB[- ]?C", n, re.I):
            f = re.findall(r"(\d{2,3})\s*W?\b", d)
            for w in f:
                ws.setdefault(int(w), n)
        elif re.match(r"USB[- ]?C\s*\(\s*Power\s*Delivery\s*(\d{2,3})\s*W", n, re.I) and not re.search(r"downstream", n, re.I):
            ws.setdefault(int(re.match(r"USB[- ]?C\s*\(\s*Power\s*Delivery\s*(\d{2,3})", n, re.I)[1]), n)
    pd = [f"{n}: {d}" for _, n, d in rows if n in set(ws.values())]
    if len(ws) == 1:
        w, n = next(iter(ws.items()))
        add("usb.usbc_pd_w", w, n)
    pwr = get("Power Consumption (max)")
    if pwr and (m := re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*W\s*", pwr)):
        add("pwr.max", float(m[1]) if "." in m[1] else int(m[1]), "Power Consumption (max)")
    vesa = get("VESA Wall Mount")
    if vesa and (m := re.fullmatch(r"\s*(\d{2,3})\s*x\s*(\d{2,3})\s*mm\s*", vesa)):
        add("ergo.vesa", f"{m[1]}x{m[2]}", "VESA Wall Mount")
    pr.fingerprints = {"raw": snap.snapshot, "labels": [f"{c} > {n}" for c, n, _ in rows][:300], "pd_rows": [x[:120] for x in pd]}
    return pr


if __name__ == "__main__":
    _run.main(BenqMonitors())
