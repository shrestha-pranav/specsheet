#!/usr/bin/env python3
"""Samsung consumer internal-SSD datasheet adapter v1 (contract ARCHITECTURE 15.5), category ssds. Source = Samsung's own datasheet PDFs as
linked from its consumer-storage documents page (https://semiconductor.samsung.com/consumer-storage/support/documents/; robots.txt Allow: /;
PDFs on semiconductor.samsung.com and download.semiconductor.samsung.com, both in data/source-policy.yaml as maker).

Why (A2-ssd, 2026-11-25): a few samsung.com/us SKU pages print no DRAM row (980 PRO 1TB MZ-V8P1T0B/AM: the page's Controller cell carries the
cache string, which samsung_ssd guards and drops). The datasheet's spec table prints 'DRAM Cache Memory  512MB LPDDR4  1GB LPDDR4  2GB LPDDR4'.

discover : ONE request (the documents page); every /resources/data-sheet/*.pdf link whose file name names an internal NVMe / SATA SSD line
           (portable, card and UFD sheets skipped). Hints carry the configuration keys of the stored samsung-us-ssd discovery (offline), so a
           datasheet only ever attaches to a configuration samsung_ssd already minted.
fetch    : the linked PDF (redirect followed), stored only when the body is a PDF. 1 req/s, honest UA.
parse    : pure over `pdftotext -layout`. ONE key, hw.dram_type. The '(DRAM) Cache Memory' / 'DRAM' row (optionally after the table's
           left group label '(Hardware) Information'): its cells are read with _ssd.dram();
           a value is written only when EVERY cell gives the same hw.dram_type (e.g. every cell names an LPDDR4 size = dram; every cell HMB =
           dramless_hmb), so no column alignment is assumed. It applies to every model code printed in the document (MZ-xxxx, incl. /AM) whose
           normalised form equals a samsung-us-ssd configuration key; anything else writes nothing.
Traps    : cells that differ (one HMB, one LPDDR4) = per-capacity, nothing read. No row = silence. Never inferred from the controller.
"""
import json, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _ssd as S
import _lt as L
import _run

ID, VERSION, SOURCE = "samsung_datasheets", 1, "samsung-ssd-datasheets"
CATEGORIES = {"ssds"}
ADAPTER = f"{ID}@{VERSION}"
PAGES = "samsung-us-ssd"
DOCS_PAGE = "https://semiconductor.samsung.com/consumer-storage/support/documents/"
DELAY = 1.0
LINK = re.compile(r'(https://(?:download\.)?semiconductor\.samsung\.com/resources/data-sheet/[^"\'<>\s]+\.pdf)')
INTERNAL = re.compile(r"nvme|ssd_8[5-7]0|ssd_9[56]0|ssd_750", re.I)
SKIP = re.compile(r"portable|warranty|micro ?sd|sd_card|ufd|express", re.I)
CODE = re.compile(r"\bMZ-[A-Z0-9]{6,}(?:/[A-Z]{2})?")
ROW = re.compile(r"^\s*(?:(?:Hardware\s+)?Information\s{2,})?(?:DRAM\s+)?Cache\s+Memory\s{2,}(\S.*?)\s*$|^\s*DRAM\s{2,}(\S.*?)\s*$", re.I)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def pdf_to_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def dram_cells(txt):
    """-> (row literal, [cells]) of the first DRAM / cache-memory row, else (None, [])."""
    for ln in txt.splitlines():
        m = ROW.match(ln)
        if m:
            cell = m[1] or m[2]
            return ln.strip(), [c for c in re.split(r"\s{2,}", cell) if c.strip()]
    return None, []


def dram_value(cells):
    vals = {dict(S.dram(c)).get("hw.dram_type") for c in cells}
    return vals.pop() if len(vals) == 1 and None not in vals else None


def parse_text(snap, txt):
    pr = C.ParseResult()
    pr.sources = [{**L.source(snap, "Samsung SSD datasheet " + snap.ref.key), "url": snap.final_url or snap.ref.url}]
    known = set((snap.ref.hints or {}).get("configs") or [])
    raw, cells = dram_cells(txt)
    v = dram_value(cells)
    codes = list(dict.fromkeys(CODE.findall(txt)))
    tied = [c for c in codes if norm(c) in known]
    for code in tied:
        pr.identifiers.append(L.ident("mfr_sku", code, "configuration", "samsung"))
        if v:
            S.add(pr, ADAPTER, snap, "hw.dram_type", v, raw, "sku", code, "DRAM cache (datasheet spec table)")
    if not tied:
        pr.absences.append({"key": "*", "reason": "no model code tied to a samsung-us-ssd configuration", "source": "s1"})
    pr.fingerprints = {"raw": snap.snapshot, "row": raw, "cells": cells, "codes": codes, "tied": tied}
    return pr


class SamsungDatasheets:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps = C.BlobStore(PAGES)
        configs = sorted({norm(r["key"]) for r in json.loads((ps.dir / "discovery.json").read_text())["refs"]})
        r = net.get(DOCS_PAGE, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            return C.Discovery([], False, None, {"error": str(getattr(r, "status_code", r))})
        refs = []
        for u in sorted(set(LINK.findall(r.text))):
            name = u.rsplit("/", 1)[-1]
            if INTERNAL.search(name) and not SKIP.search(name):
                refs.append(C.Ref(SOURCE, Path(name).stem.lower(), u, {"configs": configs, "linked_from": DOCS_PAGE}))
        return C.Discovery(refs, True, None, {"datasheets": len(refs)})

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
    _run.main(SamsungDatasheets())
