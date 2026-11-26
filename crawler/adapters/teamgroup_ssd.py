#!/usr/bin/env python3
"""TEAMGROUP (T-FORCE / T-CREATE / TEAMGROUP) SSD adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = www.teamgroupinc.com/en/.

discover : /en/sitemap.xml lists only ~31 SSD product-detail URLs, so the m2/internal/external category pages (?page=N until no new links,
           capped) are walked too (~12 requests). One Ref per MODEL directory (cardea-z44l, mp44, g50 ...); hints.urls = every per-capacity
           product-detail URL seen. robots.txt: only /public/lineBot and /*/act* disallowed.
fetch    : the representative product-detail page (200 KB), stored gzip. 1 req/s.
parse    : pure. The page's 'specTable' has one row per capacity: Model | Capacity | Sequential Read | Sequential Write | Terabyte Written |
           DRAM Cache | TEAM P/N (column set varies, header-driven). 'More Product Specifications' (div.leftTitle/div.text) holds Interface,
           Operation Temperature, Weight, Dimensions, MTBF and applies to every row. configuration = TEAM P/N (TM8FPP002T0C129);
           model key = P/N stem before the capacity token (TM8FPP); trailing C1xx/C3xx = package/revision-style batch code (kept as an
           x_batch_code alias, NOT assumed to be a hardware revision).
Traps    : read/write 'up to' speeds differ per capacity (512GB write 2,500 vs 4,500 MB/s): claims are per configuration; 'DRAM Cache: NO' = DRAM-less
           but HMB use is not stated (dramless_none is only emitted when the cell says NO and the interface is NVMe/SATA: recorded as printed);
           'Terabyte Written 1200TBW' is TB; controller/NAND vendor are never in the table (some pages name them in prose).
v3 (2026-11-24): NAND type, controller (vendor) and HMB from explicit page-prose statements (_ssdprose.py), quote kept as raw, only where
           the table is silent; 'DRAM Cache: NO' + a stated HMB = dramless_hmb.
v4 (coverage r3): version bump for _ssdprose.py: a bare 'DRAM-less' sentence about the drive (no HMB in it) = hw.dram_type `dramless`
           (HMB unstated, hw.hmb_support left unknown). Nothing else changed.
v6 (A2-st r7, 2026-11-26): hw.nand_type from an intro paragraph (div.prIntro) read on its own, only when the whole-page prose pass found
           no NAND statement and no NAND conflict. The page pass misses it when the paragraph runs on from the nav text with no sentence
           break (a > 600-char 'sentence' is skipped): CARDEA Z44Q 'adopts QLC Flash', Z44A7Q 'The product adopts 3D QLC NAND'. The same
           _ssdprose rules apply per paragraph (hedges, comparisons, two models = nothing); two different values across paragraphs = nothing.
           Only hw.nand_type is taken from this pass; every other claim is byte-identical to v5.
"""
import gzip, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _ssd as S
import _lt as L
import _ssdprose as SP
import _run

INTRO = re.compile(r'<div class="prIntro">(.*?)</div>', re.S)
ID, VERSION, SOURCE = "teamgroup_ssd", 6, "teamgroup-us-ssd"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.teamgroupinc.com"
DELAY = 1.0
CATS = ["m2", "internal", "external"]
DETAIL = re.compile(r'(https://www\.teamgroupinc\.com/en/product-detail/+ssd/[^"\'<>\s]+)')
ROW = re.compile(r'<tr class="specTableRow specTableRowContent">(.*?)</tr>', re.S)
CELL = re.compile(r'<td class="specTableColumn">(.*?)</td>', re.S)
HEAD = re.compile(r'<th class="specTableColumn" data-name="([^"]*)"')
KV = re.compile(r'<div class="leftTitle">(.*?)</div>\s*<div class="text">(.*?)</div>', re.S)
PN = re.compile(r"^(TM\d[A-Z0-9]{4})(\d{3}[GT]\d)(C\d{3})$")


def model_dir(u):
    p = u.split("/product-detail/", 1)[1].strip("/").split("/")
    return p[2] if len(p) >= 4 else p[1]


class TeamgroupSsd:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        urls, stop = set(), None
        sm = net.get(BASE + "/sitemap.xml", DELAY)
        if hasattr(sm, "status_code") and sm.status_code == 200:
            urls |= {u.replace("detail//", "detail/") for u in DETAIL.findall(sm.text)}
        else:
            stop = f"sitemap {getattr(sm, 'status_code', sm)}"
        for cat in CATS:
            for page in range(1, 9):
                r = net.get(f"{BASE}/en/product-category/ssd/{cat}/" + (f"?page={page}" if page > 1 else ""), DELAY)
                if not hasattr(r, "status_code") or r.status_code != 200:
                    stop = stop or f"category {cat} p{page}: {getattr(r, 'status_code', r)}"
                    break
                new = {u.replace("detail//", "detail/") for u in DETAIL.findall(r.text)} - urls
                if not new:
                    break
                urls |= new
        by = {}
        for u in sorted(urls):
            by.setdefault(model_dir(u), []).append(u)
        refs = [C.Ref(SOURCE, m, us[0], {"urls": us}) for m, us in sorted(by.items())]
        return C.Discovery(refs, stop is None, stop, {"models": len(refs), "urls": len(urls)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        for alt in ref.hints.get("urls", []):        # a stale sitemap URL 404s while a sibling-capacity page of the same model is live
            if hasattr(r, "status_code") and r.status_code == 404 and alt != ref.url:
                r = net.get(alt, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        s = C.Snapshot(self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz"), ref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def parse_html(snap, h):
    pr, obs = C.ParseResult(), snap.fetched_at
    pr.sources = [L.source(snap, "TEAMGROUP product page " + snap.ref.key)]
    heads = HEAD.findall(h)
    rows = [[S.clean(c) for c in CELL.findall(m)] for m in ROW.findall(h)]
    if not heads or not rows:
        pr.absences.append({"key": "*", "reason": "no specTable rows", "source": "s1"})
        return pr
    kv = {}
    for a, b in KV.findall(h):
        kv.setdefault(S.clean(a), S.clean(b))
    text = S.clean(h)
    warranty = re.search(r"(\d+)[- ]year limited warranty", text, re.I)
    series = snap.ref.key
    unmapped = {}
    prose = SP.extract(h)
    if "hw.nand_type" not in prose["claims"] and "hw.nand_type" not in prose["conflicts"]:       # v6: per intro paragraph
        got = {}
        for block in INTRO.findall(h):
            r = SP.extract(block)
            if "hw.nand_type" in r["conflicts"]:
                got = {"conflict": None, "x": None}
                break
            if "hw.nand_type" in r["claims"]:
                v, q = r["claims"]["hw.nand_type"]
                got.setdefault(v, q)
        if len(got) == 1:
            (v, q), = got.items()
            prose["claims"]["hw.nand_type"] = (v, q)
    for cells in rows:
        R = dict(zip(heads, cells))
        part = R.get("TEAM P/N") or R.get("P/N") or ""
        if not part:
            continue
        m = PN.match(part)
        stem = m[1] if m else re.sub(r"\d{3}[GT]\d.*$", "", part)
        pr.identifiers.append(L.ident("mfr_model", stem, "model", "team", series=series))
        pr.identifiers.append(L.ident("mfr_sku", part, "configuration", "team", parent=stem))
        if m:
            pr.identifiers.append(L.ident("x_batch_code", m[3], "package", "team", role="alias"))
        if R.get("Model"):
            pr.aliases.append({"text": f"{R['Model']} {R.get('Capacity', '')}".strip(), "kind": "marketing_name"})
        used = {"TEAM P/N", "Model", "Compare"}

        def add(k, v, raw, label):
            S.add(pr, ADAPTER, snap, k, v, raw, "sku", part, label)
        for lab in ("Capacity", "Sequential Read", "Sequential Write", "Terabyte Written", "DRAM Cache"):
            if lab in R:
                used.add(lab)
        if R.get("Capacity"):
            add("gen.capacity", S.capacity_gb(R["Capacity"]), R["Capacity"], "Capacity")
        if R.get("Sequential Read"):
            add("perf.seq_read", S.speed_mbs(R["Sequential Read"]), R["Sequential Read"], "Sequential Read")
        if R.get("Sequential Write"):
            add("perf.seq_write", S.speed_mbs(R["Sequential Write"]), R["Sequential Write"], "Sequential Write")
        if R.get("Terabyte Written") and re.match(r"[\d,]+", R["Terabyte Written"]):
            add("end.tbw", S.n(re.match(r"[\d,]+", R["Terabyte Written"])[0]), R["Terabyte Written"], "Terabyte Written")
        d = R.get("DRAM Cache")
        hmb = prose["claims"].get("hw.dram_type", (None,))[0] == "dramless_hmb"
        if d and re.fullmatch(r"no", d, re.I):         # v3: 'NO' + an explicit HMB statement on the page = dramless_hmb (both literals kept)
            add("hw.dram_type", "dramless_hmb" if hmb else "dramless", f"DRAM Cache: {d}; {prose['claims']['hw.dram_type'][1]}" if hmb else d,
                "DRAM Cache + page prose" if hmb else "DRAM Cache")
        elif d and re.fullmatch(r"yes", d, re.I):
            add("hw.dram_type", "dram", d, "DRAM Cache")
        iface = kv.get("Interface") or ""
        if iface:
            if re.search(r"USB|thunderbolt", iface, re.I):
                add("if.usb_standard", S.usb(iface), iface, "Interface")
                add("gen.device_class", "portable_usb", iface, "Interface")
                add("if.protocol", S.usb_protocol(iface), iface, "Interface")      # v5: affirmative USB interface only (ruling 4)
            elif re.search(r"SATA", iface, re.I):
                add("if.protocol", "sata_ahci", iface, "Interface")
            else:
                for k, x in S.interface(iface):
                    add(k, x, iface, "Interface")
        ff = S.form_factor((R.get("Model") or "") + " " + kv.get("Form Factor", "") + " " + kv.get("Dimensions", "")) or None
        dm = re.search(r"([\d.]+)\s*(?:\(L\))?\s*x\s*([\d.]+)\s*(?:\(W\))?", kv.get("Dimensions", ""))
        if ff:
            add("gen.form_factor", ff, R.get("Model") or kv.get("Form Factor"), "Model/Form Factor")
        elif dm and re.search(r"SATA", iface, re.I) and 99 <= float(dm[1]) <= 101 and 69 <= float(dm[2]) <= 70.5:
            add("gen.form_factor", "sata_2_5", kv["Dimensions"], "Dimensions (100 x 69.9 mm = 2.5in)")
        elif dm and float(dm[2]) == 22 and re.search(r"M\.?2|NVMe|PCIe", (R.get("Model") or "") + iface + kv.get("Dimensions", ""), re.I) \
                and {"30": "m2_2230", "42": "m2_2242", "60": "m2_2260", "80": "m2_2280", "110": "m2_22110"}.get(str(int(float(dm[1])))):
            add("gen.form_factor", {"30": "m2_2230", "42": "m2_2242", "60": "m2_2260", "80": "m2_2280", "110": "m2_22110"}[str(int(float(dm[1])))],
                kv["Dimensions"], "Dimensions (22 mm wide M.2 card: length = size code)")
        if (v := kv.get("Operation Temperature") or kv.get("Operating Temperature")) and (t := S.temp_range(v)):
            add("therm.temp_operating", t, v, "Operation Temperature")
        if (v := kv.get("Weight")) and (mm := re.match(r"([\d.]+)\s*g\b", v)):
            add("gen.weight", float(mm[1]), v, "Weight")
        if (v := kv.get("MTBF")) and (mm := re.match(r"([\d,]+)\s*Hours", v, re.I)):
            add("end.mtbf", S.n(mm[1]), v, "MTBF")
        if warranty:
            add("end.warranty_years", int(warranty[1]), warranty[0], "Features")
        have = {c["key"] for c in pr.claims if c["locator"].get("sku") == part}
        for k, (v, q) in prose["claims"].items():          # v3: explicit page-prose statements, only where the spec table is silent
            if k not in have and not (k == "hw.dram_type" and d and re.fullmatch(r"yes|no", d, re.I)):
                add(k, v, q, "page prose")
        unmapped[part] = {k: v for k, v in R.items() if k not in used}
    pr.fingerprints = {"raw": snap.snapshot, "series": series, "rows": len(rows), "more_specs": sorted(kv), "unmapped": unmapped,
                       "sitemap_urls": snap.ref.hints.get("urls"), "prose_conflicts": prose["conflicts"]}
    return pr


if __name__ == "__main__":
    _run.main(TeamgroupSsd())
