#!/usr/bin/env python3
"""SanDisk / WD internal SSD datasheet adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = the maker's own datasheet PDFs that the
sandisk.com line pages link ('/tools/documentRequestHandler?docPath=...', which redirects to documents.sandisk.com; both hosts are in
data/source-policy.yaml; www.sandisk.com robots.txt allows /tools/, documents.sandisk.com serves no robots.txt).

Why: sandisk.com spec tables carry no DRAM row (see sandisk_ssd.py traps). Several datasheets do: 'DRAM  Yes' (WD_BLACK SN8100, NAS 800) or
'DRAM CACHE  Yes' / 'DRAM CACHE  Host Memory Buffer' (the Optimus lines). Coordinator ruling 3 (2026-11-24 r2): use them, affirmative only.

discover : offline over the stored sandisk-us-ssd line pages (no request): every internal-ssd line page's datasheet links. One Ref per (line,
           datasheet); hints carry the line slug and the page's (Model Number, orderable SKU) pairs so a datasheet model number is tied to the
           configuration the line page defines (configuration-level mfr_sku only: no model identifier, no parent link of its own).
fetch    : the page's own datasheet link (redirect followed), stored as-is (.pdf) only when the body is a PDF. 1 req/s, honest UA.
parse    : pure over `pdftotext -layout`. The PRODUCT SPECIFICATIONS table: 'MODEL NUMBERS' row(s) list one model number per capacity column; a
           'DRAM' / 'DRAM CACHE' row whose value is ONE cell spanning every column applies to every listed model number. Yes -> dram;
           'Host Memory Buffer' / HMB -> dramless_hmb; DRAM-less / None / No -> _ssd.dram (ruling 5). A model number is matched to the line page's
           Model Number or orderable SKU (equal, or one is the other plus a '-suffix'); no match or two matches = nothing.
Traps    : a datasheet without a DRAM row (SN850X, SN770M, SN5100, SN3000) is silence, never DRAM-less. Only hw.dram_type is read here; NAND,
           speeds and the rest stay with the line page (one source per fact, no double counting).
"""
import gzip, json, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _ssd as S
import _lt as L
import _run

ID, VERSION, SOURCE = "sandisk_datasheets", 1, "sandisk-us-ssd-datasheets"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
PAGES = "sandisk-us-ssd"
HANDLER = "https://www.sandisk.com/tools/documentRequestHandler?docPath="
DELAY = 1.0
DOC = re.compile(r'docPath=(/content/dam/[^"\'<>&\s]*/internal-drives/[^"\'<>&\s]*data-sheet[^"\'<>&\s]*\.pdf)')
MN = re.compile(r"\b(?:WDS|WDB|SDS|SDB|SDF)[A-Z0-9]{6,}(?:-[A-Z0-9]{4,6})?\b")
DRAM_ROW = re.compile(r"^\s*DRAM(?: CACHE)?\d*\s{2,}(\S.*?)\s*$")


def pdf_to_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def spec_table(txt):
    """-> (model numbers in column order, DRAM cell text or None). The DRAM cell must be one spanning value (no wide gap inside it)."""
    mns, cell = [], None
    lines = txt.splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^\s*MODEL NUMBERS?\b", ln, re.I):
            mns += MN.findall(ln)
            for nxt in lines[i + 1:i + 3]:            # a wrapped model-number row continues on the next line(s) without a label
                if nxt.strip() and not re.match(r"^\s*[A-Z][A-Za-z ]{3,}\s{2,}", nxt) and MN.search(nxt):
                    mns += MN.findall(nxt)
        m = DRAM_ROW.match(ln)
        if m and cell is None:
            cell = m[1] if not re.search(r"\S\s{3,}\S", m[1]) else ""     # several values across columns = per-capacity: not read
    return list(dict.fromkeys(mns)), cell


def dram_value(cell):
    if cell is None or cell == "":
        return None
    if re.fullmatch(r"yes", cell.strip(), re.I):
        return "dram"
    got = dict(S.dram(cell))
    return got.get("hw.dram_type")


def match(mn, configs):
    """datasheet model number -> the one (part, sku) of the line page it names, else None."""
    def same(a, b):
        return a == b or a.startswith(b + "-") or b.startswith(a + "-")
    hits = [(p, s) for p, s in configs if same(mn, p) or same(mn, s)]
    return hits[0] if len({p for p, _ in hits}) == 1 else None


def parse_text(snap, txt):
    pr = C.ParseResult()
    pr.sources = [{**L.source(snap, "SanDisk/WD datasheet " + snap.ref.key), "url": snap.final_url or snap.ref.url}]
    h = snap.ref.hints or {}
    line, configs = h.get("line"), [tuple(x) for x in h.get("configs") or []]
    mns, cell = spec_table(txt)
    v = dram_value(cell)
    if not line or not configs or not mns:
        pr.absences.append({"key": "*", "reason": "no MODEL NUMBERS row or no line-page configurations to tie it to", "source": "s1"})
        return pr
    tied, unmatched = {}, []
    for mn in mns:
        hit = match(mn, configs)
        if hit:
            tied.setdefault(hit[0], mn)
        else:
            unmatched.append(mn)
    for part, mn in tied.items():
        # configuration key only (no model, no parent): the datasheet attaches to the configuration the line page minted and never adds a link
        pr.identifiers.append(L.ident("mfr_sku", part, "configuration", "western digital"))
        if v:
            S.add(pr, ADAPTER, snap, "hw.dram_type", v, f"MODEL NUMBERS: {' '.join(mns)} | DRAM: {cell}", "sku", part, "DRAM (datasheet spec table)")
    pr.fingerprints = {"raw": snap.snapshot, "line": line, "model_numbers": mns, "dram_cell": cell, "unmatched": unmatched}
    return pr


class SandiskDatasheets:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        import sandisk_ssd as P
        ps = C.BlobStore(PAGES)
        kinds = {r["key"]: (r.get("hints") or {}).get("kind") for r in json.loads((ps.dir / "discovery.json").read_text())["refs"]}
        latest = {}
        for s in ps.snapshots():
            if s["status"] == 200:
                latest[s["ref"]] = s
        refs = []
        for key, s in sorted(latest.items()):
            if kinds.get(key) != "internal-ssd":
                continue
            h = gzip.decompress(ps.read_rec(s)).decode("utf-8", "replace")
            snap = C.Snapshot(s["snapshot"], C.Ref(PAGES, key, s["url"], {}), 200, s["fetched_at"], s["final_url"], {})
            pr = P.parse_html(snap, h)
            configs, part = set(), None
            for i in pr.identifiers:                   # the line page emits (mfr_model, mfr_sku, x_orderable_sku) per SKU, in that order
                if i["scheme"] == "mfr_sku":
                    part = i["value"]
                elif i["scheme"] == "x_orderable_sku" and part:
                    configs.add((part, i["value"]))
            configs = sorted(configs)
            for doc in sorted(set(DOC.findall(h))):
                stem = Path(doc).stem
                refs.append(C.Ref(SOURCE, f"{key}--{stem}", HANDLER + doc, {"line": key, "doc_path": doc, "configs": [list(c) for c in configs]}))
        return C.Discovery(refs, True, None, {"datasheets": len(refs), "pages": len(latest)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200 or r.content[:4] != b"%PDF":
            st = r if (r is None or isinstance(r, str)) else (r.status_code if r.status_code != 200 else "not_pdf")
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".pdf")
            return s
        s = C.Snapshot(self.store.put(r.content, ".pdf"), ref, 200, now, r.url, {})
        self.store.append(s, ADAPTER, ".pdf")
        return s

    def parse(self, snap, blobs, profile):
        return parse_text(snap, pdf_to_text(blobs.path(snap.snapshot, ".pdf")))


if __name__ == "__main__":
    _run.main(SandiskDatasheets())
