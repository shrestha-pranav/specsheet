#!/usr/bin/env python3
"""Kingston client SSD adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = Kingston's own datasheet PDFs (www.kingston.com/datasheets/).

Access (2026-11-24, one polite probe each, honest UA): kingston.com product pages and /siteindex.xml answer a Cloudflare challenge (403) -> NOT used
(recorded in research/ssds/merchants.md as blocked). robots.txt allows /datasheets/, and the datasheet PDFs answer 200 to the same honest client,
so ONLY the datasheets are fetched. There is no reachable index of them, so discovery is a fixed seed list of datasheet stems found by web search
(site:kingston.com/datasheets) and confirmed by one GET each; a stem that 404s is dropped, never guessed further.
discover : SEEDS -> one Ref per datasheet (key = stem, url = /datasheets/<stem>_us.pdf).
fetch    : the PDF, stored as-is (.pdf). 1 req/s.
parse    : pure over `pdftotext -layout`. Each 'Specifications [form factor]' block = label column + value column; continuation lines (no label) belong
           to the previous label. 'Part Numbers [form factor]' blocks list the orderable part numbers (SNV3S/1000G, SFYR2S/2T0). configuration = part
           number; model = part-number stem before '/' (SNV3S vs SNV3SM3 = the 2280 vs 2230 build). A part number is tied to its spec block by the
           form factor in the two headers (or to the only block); its capacity = the block's listed capacity within 10% of the number in the part
           number ('1T0' -> 1024GB on a 1024GB-list datasheet). Per-capacity rows ('512GB – 7,000/3,900MB/s', '2TB - 4TB – ...' ranges) are applied
           per configuration; a row that does not name the capacity writes nothing for it.
Traps    : 'NAND 3D' says nothing about bits per cell (no hw.nand_type); 'Gen 4x4 NVMe controller' names no controller (no hw.controller); a missing
           'DRAM Cache' row is silence, not DRAM-less; TBW in PB ('1.6PBW', '1.0PB') converted to TB as printed x1000; speeds are the datasheet's
           figures, 'up to' kept in raw.
"""
import re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _ssd as S
import _lt as L
import _run

ID, VERSION, SOURCE = "kingston_ssd", 1, "kingston-us-ssd"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.kingston.com/datasheets/"
DELAY = 1.0
SEEDS = ["SNV3S", "SNV2S", "SNVS", "KC3000", "SFYR", "SFYR2S", "SA400", "SA2000", "SXS2000"]   # 200 on 2026-11-24; 404: SKC600 SKC2500 SFYRD SNV3D (and _us variants)
CTRL_VENDOR = [(r"phison|\bE\d{2}T?\b|\bPS50\d\d", "phison"), (r"silicon motion|\bSM2\d{3}", "silicon_motion"), (r"marvell", "marvell"),
               (r"innogrit|\bIG5\d{3}", "innogrit"), (r"maxio|\bMAP1\d{3}", "maxio")]
FF = re.compile(r"M\.2\s*22(?:30|42|60|80|110)|2\.5\s*[\"”]|mSATA", re.I)
CAP = r"(\d+(?:\.\d+)?)\s*(GB|TB)"


def pdf_to_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def gb(num, unit):
    v = float(num) * (1000 if unit.upper() == "TB" else 1)
    return int(v) if v == int(v) else v


def ffkey(s):
    m = FF.search(s or "")
    return re.sub(r"\s+", "", m[0]).lower().replace("”", '"') if m else None


def blocks(txt):
    """-> (spec blocks [{ff, rows: {label: [lines]}}], part blocks [{ff, pns}])."""
    specs, parts, cur, mode, last = [], [], None, None, None
    for ln in txt.splitlines():
        s = ln.strip()
        if not s:
            continue
        if re.match(r"^Specifications\b", s):
            cur = {"ff": ffkey(s), "rows": {}}; specs.append(cur); mode, last = "spec", None; continue
        if re.match(r"^Part Numbers\b", s):
            if not parts or parts[-1]["pns"] or parts[-1]["head"] != s:
                parts.append({"ff": ffkey(s), "head": s, "pns": []})
            mode = "pn"; continue
        if mode == "pn":
            pns = re.findall(r"\b([A-Z0-9]{3,12}/\d+[GT]\d?)\b", s)
            if pns:
                parts[-1]["pns"] += pns
            elif re.match(r"^\d\.\s", s) or len(s) > 60:
                mode = None
            elif FF.search(s) and parts:          # 'M.2 2230' / '2.5” (Standalone)' sub-header inside a part-number block
                parts.append({"ff": ffkey(s), "head": s, "pns": []})
            continue
        if mode != "spec":
            continue
        m = re.match(r"^\s{0,12}([A-Z][A-Za-z0-9 /()'.-]{1,45}?)\d?\s{2,}(\S.*)$", ln)
        if m and not re.match(r"^\s{14,}", ln):
            last = re.sub(r"\d+$", "", m[1].strip()).strip().lower()
            cur["rows"].setdefault(last, []).append(m[2].strip())
        elif last and re.match(r"^\s{14,}\S", ln) and not re.fullmatch(r"\d{1,2}", s):
            cur["rows"][last].append(s)
        elif re.match(r"^\d\.\s", s):
            mode = None
    return specs, [p for p in parts if p["pns"]]


def per_cap(lines, caps):
    """'512GB – 7,000/3,900MB/s' / '2TB - 4TB – x' / '4096GB – 8192GB - up to x' -> {capacity_gb: value text}; unprefixed single line -> all."""
    out = {}
    for l in lines:
        m = re.match(r"^" + CAP + r"(?:\s*[-–—]\s*" + CAP + r")?\s*[-–—]\s*(.+)$", l)
        if m:
            lo = gb(m[1], m[2]); hi = gb(m[3], m[4]) if m[3] else lo
            for c in caps:
                if lo <= c <= hi or (abs(c - lo) / c < 0.1) or (abs(c - hi) / c < 0.1):
                    out.setdefault(c, m[5].strip())
    if not out and len(lines) == 1:
        out = {c: lines[0] for c in caps}
    return out


def pn_gb(pn):
    t = pn.split("/", 1)[1]
    m = re.match(r"(\d+)G", t)
    if m:
        return int(m[1])
    m = re.match(r"(\d+)T", t)
    return int(m[1]) * 1000 if m else None


def parse_text(snap, txt):
    pr = C.ParseResult()
    pr.sources = [L.source(snap, "Kingston datasheet " + snap.ref.key)]
    title = next((l.strip() for l in txt.splitlines() if l.strip()), snap.ref.key)
    specs, parts = blocks(txt)
    if not specs or not parts:
        pr.absences.append({"key": "*", "reason": "no Specifications / Part Numbers block", "source": "s1"})
        return pr
    unmatched = []
    for pb in parts:
        sb = next((s for s in specs if s["ff"] and s["ff"] == pb["ff"]), None) or (specs[0] if len(specs) == 1 else None)
        if sb is None:
            unmatched += pb["pns"]; continue
        R = sb["rows"]
        caps = [gb(a, b) for a, b in re.findall(CAP, " ".join(R.get("capacities", [])))]
        for pn in dict.fromkeys(pb["pns"]):
            n_ = pn_gb(pn)
            cap = next((c for c in caps if n_ and abs(c - n_) / c < 0.1), None)
            if cap is None:
                unmatched.append(pn); continue
            stem = pn.split("/")[0]
            pr.identifiers.append(L.ident("mfr_model", stem, "model", "kingston", series=snap.ref.key))
            pr.identifiers.append(L.ident("mfr_sku", pn, "configuration", "kingston", parent=stem))
            pr.aliases.append({"text": f"{title} {cap}GB", "kind": "marketing_name"})

            def add(k, v, raw, label):
                S.add(pr, ADAPTER, snap, k, v, raw, "sku", pn, label)

            def row(*names):
                for nm in names:
                    if nm in R:
                        return R[nm]
                return None
            add("gen.capacity", cap, " ".join(R["capacities"]), "Capacities")
            ffv = " ".join(row("form factor") or [])
            add("gen.form_factor", S.form_factor(ffv), ffv, "Form factor")
            iface = " ".join(row("interface") or [])
            if re.search(r"USB", iface):
                add("if.usb_standard", S.usb(iface), iface, "Interface")
                add("gen.device_class", "portable_usb", iface, "Interface")
            else:
                for k, x in S.interface(iface):
                    add(k, x, iface, "Interface")
                if re.search(r"NVMe", iface) and not re.search(r"PCIe", iface):
                    add("if.protocol", "nvme", iface, "Interface")
            if (c := row("controller")) and not re.search(r"(?i)^gen\s*\d|nvme controller$", c[0]):
                add("hw.controller", c[0], c[0], "Controller")
                add("hw.controller_vendor", next((v for rx, v in CTRL_VENDOR if re.search(rx, c[0], re.I)), None), c[0], "Controller")
            if (nd := row("nand")):
                add("hw.nand_type", S.nand_type(nd[0]), nd[0], "NAND")
            if (d := row("dram cache")):
                add("hw.dram_type", "dram" if re.fullmatch(r"(?i)yes", d[0]) else None, d[0], "DRAM cache")
            sq = row("sequential read/write", "sequential read / write")
            if sq and (v := per_cap(sq, caps).get(cap)) and (m := re.search(r"([\d,]+)\s*/\s*([\d,]+)\s*MB/s", v)):
                add("perf.seq_read", S.n(m[1]), v, "Sequential Read/Write")
                add("perf.seq_write", S.n(m[2]), v, "Sequential Read/Write")
            bl = row("baseline performance")
            if bl and (v := per_cap([l for l in bl if re.match(CAP, l)], caps).get(cap)) and (m := re.search(r"([\d,]+)\s*MB/s Read and ([\d,]+)\s*MB/s Write", v)):
                add("perf.seq_read", S.n(m[1]), v, "Baseline Performance")
                add("perf.seq_write", S.n(m[2]), v, "Baseline Performance")
            tb = row("total bytes written (tbw)", "endurance (total bytes written)", "endurance (total bytes written)")
            tb = tb or next((R[k] for k in R if "bytes written" in k), None)
            if tb and (v := per_cap(tb, caps).get(cap)) and (m := re.match(r"\s*([\d,.]+)\s*(TB|PB)", v)):
                add("end.tbw", S.n(m[1]) * (1000 if m[2] == "PB" else 1), v, "Total Bytes Written")
            if (w := row("warranty/support")):
                add("end.warranty_years", S.years(w[0]), w[0], "Warranty/Support")
            mt = row("mtbf", "life expectancy")
            if mt and (m := re.search(r"([\d,.]+)\s*(million)?\s*hours", mt[0], re.I)):
                add("end.mtbf", int(float(m[1].replace(",", "")) * (1e6 if m[2] else 1)), mt[0], "MTBF")
            if (t := row("operating temperature")) and (tr := S.temp_range(t[0])):
                add("therm.temp_operating", tr, t[0], "Operating temperature")
    pr.fingerprints = {"raw": snap.snapshot, "title": title, "spec_blocks": [{"ff": s["ff"], "labels": sorted(s["rows"])} for s in specs],
                       "part_blocks": [{"ff": p["ff"], "pns": p["pns"]} for p in parts], "unmatched_pns": unmatched}
    return pr


class KingstonSsd:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        refs = [C.Ref(SOURCE, s, f"{BASE}{s}_us.pdf", {"seed": "web search site:kingston.com/datasheets, 2026-11-24"}) for s in SEEDS]
        return C.Discovery(refs, True, None, {"seeds": len(SEEDS)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200 or r.content[:4] != b"%PDF":
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".pdf")
            return s
        s = C.Snapshot(self.store.put(r.content, ".pdf"), ref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".pdf")
        return s

    def parse(self, snap, blobs, profile):
        return parse_text(snap, pdf_to_text(blobs.path(snap.snapshot, ".pdf")))


if __name__ == "__main__":
    _run.main(KingstonSsd())
