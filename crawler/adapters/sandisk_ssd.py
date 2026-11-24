#!/usr/bin/env python3
"""SanDisk + WD consumer SSD adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = www.sandisk.com (US). Since the 2025 split,
WD_BLACK / WD_BLUE / WD_GREEN / WD_RED / My Passport SSDs are sold and specified on sandisk.com, so ONE source covers both brands
(brand = 'western digital' per research/ssds/category.yaml alias; the product line keeps its WD or SanDisk name).

discover : https://www.sandisk.com/products-sitemap.xml (one request; robots allows it, sitemap-index lists it) -> '<line>?sku=<orderable>' URLs under
           /products/ssd/internal-ssd/ and /products/ssd/external-ssd/. Grouped by product-line slug (one Ref per line, hints.skus = every orderable
           SKU the sitemap lists). Dropped: enterprise (ultrastar, dc-), test pages, industrial (ix-), recertified/clearance/embedded/sdb copies.
fetch    : the line page (AEM SSR, ~2.5 MB because every SKU variant is inlined) stored gzip (.html.gz, ~10x smaller). 1 req/s, honest UA.
parse    : pure. Per-SKU blocks: <div class='product-title' data-sku data-sku-title> (title) and the 'product-tech-specs-store' blocks
           <div data-sku=X> with label/value pairs (Capacity, Form Factor, Interface, Sequential Read/Write Performance, Random Read/Write,
           Endurance (TBW), Warranty, Weight, Model Number, Operating Temperature...). configuration = 'Model Number' (WDS100T2X0E);
           orderable data-sku (WDS100T2X0E-00BCA0, the '-00BCA0' tail = package/region code) is kept as an alias + the
           package-level x_orderable_sku.
Traps    : 'Endurance (TBW)' prints '600units' (it is TB written); Random Read/Write '800K IOPS' carries no queue depth (not mapped to qd32);
           no controller/NAND/DRAM rows exist on these pages (WD never prints them = the silent-revision problem); the same Model Number can
           appear under two orderable suffixes (-00BCA0 vs -00CDD0 on the 8TB SN850X): a candidate revision signal, recorded not decided.
v3 (2026-11-24): NAND type/vendor, controller (vendor) and HMB from explicit page-prose statements (_ssdprose.py), quote kept as raw,
           only where the spec table is silent for that SKU.
v4 (coverage r3): version bump for _ssdprose.py: a bare 'DRAM-less' sentence about the drive (no HMB in it) = hw.dram_type `dramless`
           (HMB unstated, hw.hmb_support left unknown). Nothing else changed.
"""
import gzip, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _ssd as S
import _lt as L
import _ssdprose as SP
import _run

ID, VERSION, SOURCE = "sandisk_ssd", 4, "sandisk-us-ssd"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.sandisk.com"
SITEMAP = BASE + "/products-sitemap.xml"
DELAY = 1.0
DROP = re.compile(r"ultrastar|-dc-|/test-|/ix-|data-recovery|-case|sn861|sn655", re.I)
LOC = re.compile(r"<loc>(https://www\.sandisk\.com/products/ssd/(internal-ssd|external-ssd)/([a-z0-9-]+))\?sku=([^<]+)</loc>")
PAIR = re.compile(r'font-bold inheritPara[^>]*>\s*(.*?)\s*</div>\s*<div class="inheritPara text-grey-4">\s*(.*?)\s*</div>', re.S)
SKU_DIV = re.compile(r'<div class="(?:active|hidden)" data-sku="([^"]+)">')


class SandiskSsd:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        lines = {}
        for u, kind, slug, sku in LOC.findall(r.text):
            if DROP.search(u):
                continue
            d = lines.setdefault(slug, {"url": u, "kind": kind, "skus": []})
            if sku not in d["skus"]:
                d["skus"].append(sku)
        refs = [C.Ref(SOURCE, slug, d["url"], {"kind": d["kind"], "skus": sorted(d["skus"])}) for slug, d in sorted(lines.items())]
        return C.Discovery(refs, True, None, {"lines": len(refs), "skus": sum(len(d["skus"]) for d in lines.values())})

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


def parse_html(snap, h):
    pr, obs = C.ParseResult(), snap.fetched_at
    pr.sources = [L.source(snap, "SanDisk/WD US product page " + snap.ref.key)]
    titles = dict(re.findall(r'class="product-title[^"]*" data-sku="([^"]+)" data-sku-title="([^"]*)"', h))
    h1 = re.search(r"<h1[^>]*pdp-product-title[^>]*>(.*?)<span", h, re.S)
    line = S.clean(h1[1]) if h1 else snap.ref.key
    i0 = h.find('id="product-specifications"')
    if i0 < 0 or not titles:
        pr.absences.append({"key": "*", "reason": "no product-specifications block / sku titles (not a product page)", "source": "s1"})
        return pr
    sec = h[i0:]
    ms = list(SKU_DIV.finditer(sec))
    seen = {}
    for k, m in enumerate(ms):
        sku = m[1]
        if sku in seen:
            break                                   # the block list repeats later in the page (support section)
        end = ms[k + 1].start() if k + 1 < len(ms) else len(sec)
        seen[sku] = [(S.clean(a), S.clean(b)) for a, b in PAIR.findall(sec[m.end():end])]
    unmapped = {}
    prose = SP.extract(h)
    for sku, pairs in seen.items():
        P = {}
        for a, b in pairs:
            P.setdefault(a, b)
        part = P.get("Model Number") or sku.split("-")[0]
        model = snap.ref.key        # one model per line page: Model Number prefixes (WDS, SDSSDE61, SDFPN...) are not stable stems across capacities
        family = snap.ref.key
        pr.identifiers.append(L.ident("mfr_model", model, "model", "western digital", series=family))
        pr.identifiers.append(L.ident("mfr_sku", part, "configuration", "western digital", parent=model))
        pr.identifiers.append(L.ident("x_orderable_sku", sku, "package", "western digital", role="alias"))
        if titles.get(sku):
            pr.aliases.append({"text": S.clean(titles[sku]), "kind": "marketing_name"})
        pr.aliases.append({"text": line, "kind": "marketing_name"})
        used = set()

        def get(*names):
            for n_ in names:
                if n_ in P:
                    used.add(n_)
                    return P[n_]

        def add(k, v, raw, label):
            S.add(pr, ADAPTER, snap, k, v, raw, "sku", part, label)
        ext = snap.ref.hints.get("kind") == "external-ssd"
        add("gen.device_class", "portable_usb" if ext else None, snap.ref.hints.get("kind"), "URL class")
        if (v := get("Capacity")):
            add("gen.capacity", S.capacity_gb(v), v, "Capacity")
        if (v := get("Form Factor")):
            add("gen.form_factor", S.form_factor(v) or ("portable" if ext else None), v, "Form Factor")
        elif ext:
            add("gen.form_factor", "portable", "external-ssd", "URL class")
        if (v := get("Interface")):
            if ext or re.search(r"USB|thunderbolt", v, re.I):
                add("if.usb_standard", S.usb(v), v, "Interface")
            elif re.search(r"SATA", v, re.I):
                add("if.protocol", "sata_ahci", v, "Interface")
            else:
                for k, x in S.interface(v):
                    add(k, x, v, "Interface")
            if re.search(r"NVMe", v, re.I) and not any(c["key"] == "if.protocol" for c in pr.claims if c["locator"].get("sku") == part):
                add("if.protocol", "nvme", v, "Interface")
        if (v := get("Sequential Read Performance", "Sequential Read", "Read Speed", "Read Performance")):
            add("perf.seq_read", S.speed_mbs(v), v, "Sequential Read")
        if (v := get("Sequential Write Performance", "Sequential Write", "Write Speed", "Write Performance")):
            add("perf.seq_write", S.speed_mbs(v), v, "Sequential Write")
        if (v := get("Endurance (TBW)", "Endurance")) and re.match(r"\s*[\d,]+", v):
            add("end.tbw", S.tbw(v), v, "Endurance (TBW)")
        if (v := get("Warranty")):
            add("end.warranty_years", S.years(v), v, "Warranty")
        if (v := get("Weight")) and (m := re.search(r"([\d.]+)\s*(gms?|g|grams|oz|lbs?)\b", v, re.I)):
            u = m[2].lower()
            add("gen.weight", round(float(m[1]) * (28.3495 if u == "oz" else 453.592 if u.startswith("lb") else 1), 1), v, "Weight")
        if (v := get("Operating Temperature")) and (t := S.temp_range(v)):
            add("therm.temp_operating", t, v, "Operating Temperature")
        if (v := get("Mean Time Between Failures", "MTBF")) and (m := re.search(r"([\d,.]+)\s*(?:million)?", v, re.I)):
            add("end.mtbf", int(float(m[1].replace(",", "")) * (1e6 if re.search("million", v, re.I) else 1)), v, "MTBF")
        if (v := get("NAND")):
            add("hw.nand_type", S.nand_type(v), v, "NAND")
            add("hw.nand_vendor", S.nand_vendor(v), v, "NAND")
        if (v := get("DRAM Cache")):
            for k, x in S.dram(v) or ([("hw.dram_type", "dram")] if re.fullmatch(r"yes", v, re.I) else []):
                add(k, x, v, "DRAM Cache")
        if (v := get("Connector")) and re.fullmatch(r"USB-?C|Type-?C|USB Type-C", v, re.I):
            add("if.usb_connector", "usb_c", v, "Connector")
        if (v := get("Protocol")) and re.search(r"NVMe", v, re.I) and not any(c["key"] == "if.protocol" and c["locator"].get("sku") == part for c in pr.claims):
            add("if.protocol", "nvme", v, "Protocol")
        if not any(c["key"] == "perf.seq_read" and c["locator"].get("sku") == part for c in pr.claims) and (v := get("Transfer Rate")) and (mm := re.search(r"up to\s*([\d,.]+\s*(?:GB|MB)/s)", v, re.I)):
            add("perf.seq_read", S.speed_mbs(mm[1]), v, "Transfer Rate")
        have = {c["key"] for c in pr.claims if c["locator"].get("sku") == part}
        for k, (v, q) in prose["claims"].items():          # v3: explicit page-prose statements, only where the spec table is silent
            if k not in have:
                add(k, v, q, "page prose")
        for lab in ("Dimensions (L x W x H)", "Dimensions", "Model Number"):
            get(lab)
        unmapped[sku] = {k: v for k, v in P.items() if k not in used}
    pr.fingerprints = {"raw": snap.snapshot, "line": line, "skus": list(seen), "sitemap_skus": snap.ref.hints.get("skus"), "unmapped": unmapped,
                       "prose_conflicts": prose["conflicts"]}
    return pr


if __name__ == "__main__":
    _run.main(SandiskSsd())
