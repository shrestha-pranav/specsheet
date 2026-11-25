#!/usr/bin/env python3
"""Vizio US televisions adapter v1 (contract ARCHITECTURE 15.5), category tvs.

discover : https://www.vizio.com/products-sitemap.xml (robots `User-agent: *` Allow /) -> /en/tv/<series>/<code> pages (179). Many sitemap codes are
           retailer-era shortcodes (D40fM-K09) that 301 to the model page (/en/tv/fhd/VFD40M-0810); the fetch follows the redirect. 1 req/s.
fetch    : the server-rendered page, gzip-stored. No JSON endpoint is called: the spec table is plain HTML.
parse    : pure. Labelled rows `tech-specs_accord__row` <span>label</span><span>value</span>, grouped under their accordion heading (a label such as
           "Ports" or "Pattern" is only meaningful inside its group). Rows are renamed to the labels _tv.emit() reads and the original
           'label: value' literal is restored on every claim. Model = the Energy Guide "Model:" on the page, else the canonical URL's last segment;
           a page where those two disagree, or with no spec rows (legacy pages), yields an absence and no entity.
Identity : mfr_model = that model number verbatim (VFD40M-0810, VQD65M-0804). The sitemap shortcode is kept as x_vizio_shortcode (alias, never a key).
"""
import gzip, html, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _tv as T
import _run

ID, VERSION, SOURCE = "vizio_tvs", 3, "vizio-us-tvs"
CATEGORIES = {"tvs"}
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.0
SITEMAP = "https://www.vizio.com/products-sitemap.xml"
URL = re.compile(r"<loc>(https://www\.vizio\.com/en/tv/([a-z0-9-]+)/([^/<]+))</loc>", re.I)
ROW = re.compile(r'tech-specs_accord__row"><span>(.*?)</span><span>(.*?)</span>', re.S)
SECTION = re.compile(r'aria-label="([^"]+)">\s*<figure.*?</figure>', re.S)
# (section, label) -> label that _tv.emit() reads; section None = any
RENAME = {(None, "Class Size"): "Screen Class", (None, "High Dynamic Range"): "HDR Format Support", (None, "Dynamic Motion Rate"): "Motion Rate",
          ("HDMI Inputs", "Ports"): "HDMI", (None, "USB Ports"): "USB", (None, "Protocol Wi-Fi"): "Wi-Fi",
          ("Outputs", "ARC"): "HDMI Audio Return Channel (ARC)", (None, "Television Warranty"): "Warranty",
          (None, "Variable Refresh Rate Support"): "VRR"}


class VizioTvs:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        seen = {}
        for url, series, code in URL.findall(r.text):
            seen.setdefault(f"{series}/{code}".lower(), (url, series, code))
        refs = [C.Ref(SOURCE, k, u, {"series": s, "code": c}) for k, (u, s, c) in sorted(seen.items())]
        return C.Discovery(refs, True, None, {"tv_urls": len(refs)})

    def fetch(self, ref, prior, net):
        r = net.get(ref.url, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        sha = self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz")
        s = C.Snapshot(sha, ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        h = gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace")
        return parse_html(snap, h)


def spec_rows(h):
    """-> [(section, label, value)] in page order."""
    heads = [(m.start(), html.unescape(m.group(1))) for m in SECTION.finditer(h)]
    out = []
    for m in ROW.finditer(h):
        sec = next((n for p, n in reversed(heads) if p < m.start()), None)
        out.append((sec, T.clean(re.sub(r"<[^>]+>", " ", m.group(1))), T.clean(re.sub(r"<[^>]+>", " ", m.group(2)))))
    return out


def norm_value(label, v):
    v = re.sub(r"(\d)\s*(lbs?)\b", r"\1 \2", v)
    if re.match(r"dimensions", label, re.I):
        v = re.sub(r"\s*\([^)]*mm[^)]*\)\s*$", "", v)
    return v


def parse_html(snap, h):
    pr, obs = C.ParseResult(), snap.fetched_at
    m = re.search(r"<strong>Model:</strong>\s*([^<\s][^<]*)<", h)
    canon = re.search(r'<link rel="canonical" href="https://www\.vizio\.com/en/tv/[^/"]+/([^/"?]+)"', h)
    egm = m.group(1).strip() if m else None
    cm = canon.group(1).strip() if canon else None
    srows = spec_rows(h)
    model = egm or cm
    if not srows or not model or (egm and cm and egm.lower() != cm.lower()) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{3,24}", model):
        pr.absences.append({"key": "*", "reason": "no spec rows, or no model number / Energy Guide and canonical URL disagree", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "model": model, "energy_guide": egm, "canonical": cm, "rows": len(srows)}
        return pr
    pr.sources = [{"id": "s1", "url": snap.final_url or snap.ref.url, "label": "Vizio US product page " + model, "source_id": SOURCE,
                   "tier": "manufacturer", "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "vizio", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    code = snap.ref.hints.get("code") if snap.ref.hints else None
    if code and code.lower() != model.lower():
        pr.identifiers.append({"scheme": "x_vizio_shortcode", "value": code, "value_raw": code, "issuer": "vizio", "sources": ["s1"]})
    title = re.search(r"<title>(.*?)</title>", h, re.S)
    if title and T.clean(title.group(1)).lower() != model.lower():
        pr.aliases.append({"text": T.clean(title.group(1)), "kind": "marketing_name", "source": "s1", "observed_at": obs})
    rows, orig = {}, {}
    for sec, label, v in srows:
        new = RENAME.get((sec, label)) or RENAME.get((None, label)) or label
        if sec == "HDMI Inputs" and label == "Type":
            new = "HDMI Type"
        if sec and re.search(r"vesa|mount", sec, re.I) and label == "Pattern":
            new = "VESA Hole Pattern"
            v = re.sub(r"(\d+)\s*mm\s*x\s*(\d+)\s*mm", r"\1x\2 mm", v).replace(" mm", "")
        if new == "VRR":     # only a bare affirmative feature name counts as Yes; anything else keeps its text (no negation-blind match)
            nv = "Yes" if re.fullmatch(r"(HDMI VRR|(AMD )?FreeSync( Premium( Pro)?)?)", v, re.I) else v
        elif label == "Local Dimming Zones":
            zm = re.fullmatch(r"Yes with Active LED Zones\W*\s*x(\d{2,4})", v, re.I)
            new, nv = ("Dimming Zones", f"{zm.group(1)} zones") if zm else (label, v)
        elif label == "Refresh Rate" and len(re.findall(r"\d\s*Hz", v)) > 1:
            new, nv = "Refresh Rate (per resolution)", v           # '120Hz @UHD, 240Hz @FHD': no single native figure
        else:
            nv = norm_value(label, v)
        if new not in rows:
            rows[new] = nv
            orig[new] = (label, v)
    used = T.emit(pr, "vizio", model, rows, ADAPTER, "html_table", obs)
    for c in pr.claims:                               # restore the printed label / value in the literal
        lab = (c.get("locator") or {}).get("label")
        if lab in orig:
            ol, ov = orig[lab]
            c["raw"] = f"{ol}: {ov}"[:300]
            c["locator"] = {**c["locator"], "label": ol}
            if c.get("quote"):
                c["quote"] = c["raw"]
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "rows": len(rows), "unmapped": {k: v for k, v in rows.items() if k not in used}}
    return pr


if __name__ == "__main__":
    _run.main(VizioTvs())
