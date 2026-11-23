#!/usr/bin/env python3
"""Tripp Lite (Eaton) adapter, contract v1 (ARCHITECTURE.md 15.5). Source = per-SKU datasheet PDF.

discover : https://tripplite.eaton.com/en_sitemap.xml once (robots Crawl-delay 15 honoured for that host); product URLs end
           in ~<SKU>. Product pages are never fetched (302 -> www.eaton.com, which resets non-browser TLS).
fetch    : https://assets.tripplite.com/product-pdfs/en/<sku lower>.pdf (no robots, no block) -> blob + snapshot log.
parse    : pure over the PDF blob (pdftotext -layout): identifiers, alias, claims keyed to research/power-strips/spec-profile.yaml,
           unmapped rows kept in fingerprints (never dropped, never coerced).
Usage    : python3 -I crawler/adapters/tripplite.py discover|fetch|parse|run   (generic runner _run.py; parse is offline)
Class-style adapter (round 3): TrippLite.discover/fetch/parse(snap, blobs, profile); parse_text() is the pure text parser.
"""
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION, SOURCE = "tripplite", 2, "tripplite"
CATEGORIES = {"power-strips"}
SITEMAP = "https://tripplite.eaton.com/en_sitemap.xml"
PDF = "https://assets.tripplite.com/product-pdfs/en/{}.pdf"
DEFAULT_PATTERN = r"surge-protector|power-strip|isobar|power-center"
EXCLUDE = re.compile(r"/products/|pdu|rack-?mount|ups-|-ups|inverter|0u-|clamp|holder|in-line|ethernet|serial|poe|coax|dataline|"
                     r"data-line|cat[5-8]|replacement|mount-kit|cord-clip", re.I)
FOOTER = re.compile(r"^\s*1000 Eaton Boulevard", re.M)
ADAPTER = f"{ID}@{VERSION}"


# ------------------------------------------------------------------ discover / fetch
def _discover(checkpoint, store, net, pattern=DEFAULT_PATTERN):
    cache = store.dir / "_sitemap.xml"
    stop = None
    if not cache.exists() or (checkpoint or {}).get("refresh"):
        r = net.get(SITEMAP, 15)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        cache.write_bytes(r.content)
    urls = re.findall(r"<loc>([^<]+~[A-Za-z0-9-]+)</loc>", cache.read_text())
    pat = re.compile(pattern, re.I)
    refs = [Ref(SOURCE, sku, u, {"title_slug": u.rsplit("/", 1)[1].rsplit("~", 1)[0], "skus": [sku]})
            for sku, u in sorted({u.rsplit("~", 1)[1].upper(): u for u in urls if pat.search(u) and not EXCLUDE.search(u)}.items())]
    return Discovery(refs, True, stop, {"sitemap_urls": len(urls), "matched": len(refs)})


def pdf_to_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


# ------------------------------------------------------------------ parse (pure)
def parse_table(txt):
    """pdftotext -layout 'Specifications' table -> ({section: {label: value}}, [rows]). Stops at the Eaton footer."""
    m0 = re.search(r"^\s*Specifications\s*$", txt, re.M)
    if not m0:
        return {}
    body = txt[m0.end():]
    f = FOOTER.search(body)
    if f:
        body = body[:f.start()]
    out, sec, last, valcol = {}, None, None, None
    for ln in body.splitlines():
        s = ln.strip()
        if not s or re.fullmatch(r"\d+/\d+", s):
            continue
        if s.isupper() and len(s) > 3 and not re.search(r"\s{3,}", s):
            sec, last = s, None
            out.setdefault(sec, {})
            continue
        if sec is None:
            continue
        m = re.match(r"^(\s*)(\S.*?)\s{2,}(\S.*)$", ln)
        if m and len(m.group(1)) < 8:
            last, valcol = m.group(2).strip(), m.start(3)
            out[sec][last] = m.group(3).strip()
        elif last:
            indent = len(ln) - len(ln.lstrip())
            if valcol is not None and indent >= valcol - 2:        # wrapped value
                out[sec][last] += " " + s
            else:                                                  # wrapped label ("... (Center to" / "Center)")
                v = out[sec].pop(last)
                last = last + " " + s
                out[sec][last] = v
    for sec in out.values():                                       # layout quirk: two rows glued on one line
        for k, v in list(sec.items()):
            g = re.match(r"^(.*?)\s+(Shipping Dimensions \(hwd / cm\))\s+(.*)$", v)
            if g:
                sec[k], sec[g.group(2)] = g.group(1), g.group(3)
    return out


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    return float(m.group(0).replace(",", "")) if m else None


def yesno(s):
    s = (s or "").strip().lower()
    return True if s.startswith("yes") else False if s.startswith("no") else None


def conv(kind, raw):
    if kind == "num":
        v = num(raw); return (int(v) if v is not None and v == int(v) else v)
    if kind == "bool":
        return yesno(raw)
    if kind == "count":                                            # "(10) 5-15R" or "(6) 5-15R; (2) USB"
        n = [int(x) for x in re.findall(r"\((\d+)\)\s*5-\d", raw)]
        return sum(n) if n else None
    if kind == "text":
        return raw.strip()
    if kind == "yes_only":
        return "right_angle" if yesno(raw) else None
    return None


# label -> (profile key, unit, converter)
MAP = {
    "AC Suppression Joule Rating": ("surge.joules", "J", "num"),
    "AC Suppression Response Time": ("surge.response_time", None, "text"),
    "Maximum Surge Amps": ("surge.max_surge_current", "A", "num"),
    "AC Suppression Surge Current": ("surge.max_surge_current", "A", "num"),
    "Automatic Shut-Off": ("safety.auto_shutoff", None, "bool"),
    "Isolated Filter Banks": ("surge.isolated_banks", None, "bool"),
    "Circuit Breaker (amps)": ("load.max_amps", "A", "num"),
    "Output (Watts)": ("load.max_watts", "W", "num"),
    "Voltage Compatibility (VAC)": ("load.voltage", "V", "num"),
    "Input Cord Length (ft.)": ("cord.length_ft", "ft", "num"),
    "Input Cord Gauge (AWG)": ("cord.gauge_awg", "AWG", "num"),
    "Input Plug Type": ("cord.plug_type", None, "text"),
    "Right-Angle Plug": ("cord.plug_style", None, "yes_only"),
    "Output Receptacles": ("outlets.count", None, "count"),
    "Right-Angle Outlets": ("outlets.right_angle", None, "bool"),
    "Rotatable Outlets": ("outlets.rotating", None, "bool"),
    "Material of Construction": ("phys.material", None, "text"),
    "Unit Weight (lbs.)": ("phys.weight_lb", "lb", "num"),
    "Product Warranty Period": ("cert.warranty_years", None, "text"),
    "Number of Charging Ports": ("usb.ports", None, "num"),
    "Total Charging Watts": ("usb.total_w", "W", "num"),
}


def parse_text(ref, snap_sha, observed, pdf_text):
    """pdf_text: pdftotext output of the snapshot blob (derived deterministically from it)."""
    pr = ParseResult()
    pr.sources = [{"id": "s1", "url": PDF.format(ref.key.lower()),
                   "label": "Tripp Lite datasheet PDF", "source_id": "tripplite-datasheet", "tier": "manufacturer",
                   "retrieved_at": observed, "snapshot": snap_sha}]
    txt = pdf_text
    mm = re.search(r"MODEL NUMBER:\s*(\S+)", txt)
    model = (mm.group(1) if mm else ref.key).strip()
    title = " ".join(txt.split("MODEL NUMBER", 1)[0].split()) if mm else None
    if title:
        title = title.split(" Highlights")[0]
        pr.aliases.append({"text": title, "kind": "marketing_name", "source": "s1", "observed_at": observed})
    pr.identifiers += [{"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "tripplite", "market": "US"}]
    table = parse_table(txt)
    flat = {l: (sec, v) for sec, rows in table.items() for l, v in rows.items()}
    unmapped = {}
    for label, (sec, raw) in flat.items():
        if label == "UPC Code":
            g = re.sub(r"\D", "", raw)
            if g:
                pr.identifiers.append({"scheme": "gtin", "value": g.zfill(14), "value_raw": raw, "issuer": "GS1", "market": None})
            continue
        if label == "UL1449 Let Through Rating":      # "400V - UL Verified" or "500, 400, 500" (L-N, L-G, N-G order not stated)
            vals = [int(x) for x in re.findall(r"\d+", raw)]
            pr.claims.append(claim(model, "surge.vpr_max", max(vals) if vals else None, "V", raw, "s1", ADAPTER, "pdf_text", observed,
                                   {"section": sec, "label": label}, f"{label}  {raw}", status="known" if vals else "unknown"))
            continue
        if label == "Product Certifications":
            for key, rx in (("type.ul1449_listed", r"UL ?1449"), ("type.ul1363_listed", r"UL ?1363")):
                if re.search(rx, raw):
                    pr.claims.append(claim(model, key, True, None, raw, "s1", ADAPTER, "pdf_text", observed,
                                           {"section": sec, "label": label}, f"{label}  {raw}"))
                else:   # not named in the certifications row: absence of mention, not a claim of "false"
                    pr.absences.append({"key": key, "reason": f"not named in 'Product Certifications': {raw}", "source": "s1"})
            continue
        if label in MAP:
            key, unit, kind = MAP[label]
            v = conv(kind, raw)
            if v is None:
                unmapped[label] = raw
                continue
            if key == "cert.warranty_years":
                unmapped[label] = raw; continue
            pr.claims.append(claim(model, key, v, unit, raw, "s1", ADAPTER, "pdf_text", observed, {"section": sec, "label": label}, f"{label}  {raw}"))
        else:
            unmapped[label] = raw
    dl, dl_raw = [], []                                           # one list claim from three yes/no rows (they are one spec, `surge.dataline`)
    for label, item in (("Telephone/DSL Protection", "phone_dsl"), ("Cable (Coax) Protection", "coax"), ("Network (Ethernet) Protection", "ethernet")):
        if label in flat:
            yn = yesno(flat[label][1])
            dl_raw.append(f"{label}: {flat[label][1]}")
            if yn:
                dl.append(item)
            unmapped.pop(label, None)
    if dl_raw:
        pr.claims.append(claim(model, "surge.dataline", sorted(dl), None, "; ".join(dl_raw), "s1", ADAPTER, "pdf_text", observed,
                               {"labels": [r.split(":")[0] for r in dl_raw]}, "; ".join(dl_raw)))
    if "AC Suppression Joule Rating" not in flat:
        pr.absences.append({"key": "surge.joules", "reason": "datasheet has no joule rating row (likely plain UL 1363 strip)", "source": "s1"})
    pr.links = []
    pr.fingerprints = {"raw": snap_sha, "spec_section": sorted(flat), "unmapped": unmapped, "model": model, "sections": list(table)}
    return pr


# ------------------------------------------------------------------ adapter (class style, runner _run.py)
class TrippLite:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        return _discover(checkpoint, self.store, net)

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, PDF.format(ref.key.lower()), 1.0, ".pdf", ADAPTER)
        return snap

    def parse(self, snap, blobs, profile):
        """Pure over the PDF blob (pdftotext of the stored bytes)."""
        return parse_text(snap.ref, snap.snapshot, snap.fetched_at, pdf_to_text(blobs.path(snap.snapshot, ".pdf")))


if __name__ == "__main__":
    _run.main(TrippLite())
