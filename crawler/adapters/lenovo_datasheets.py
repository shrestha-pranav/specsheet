#!/usr/bin/env python3
"""Lenovo monitor datasheet adapter v1 (contract ARCHITECTURE 15.5), category monitors. Source = Lenovo's own one-page marketing datasheets on
psrefstuff.lenovo.com (/syspool/Sys/PDF/datasheet/<Line>_<Model>-<Gen>_datasheet_EN.pdf; the host serves no robots.txt; policy 2026-11-25.1
lists it as maker, crawl: agent). Brief pm-2026-11-25-independent-sources-a2.md #4(a): a star level or flicker statement that the PSREF
platform table omits can be read from the sheet.

discover : offline over the stored lenovo-psref-monitors snapshots (no request). One Ref per product key whose PSREF table has NO flicker
           fact already (no 'Flicker Free' line, no 'Eye Comfort Certification (5-star)' line). URL = product key minus '_Monitor', last '_'
           -> '-' (ThinkVision_T27QD_40_Monitor -> ThinkVision_T27QD-40_datasheet_EN.pdf). A 404 is recorded and means no sheet.
fetch    : one GET per product key, 1 req/s, honest UA; stored only when the body is a PDF.
parse    : pure over `pdftotext -layout`. Identity = the product key (mfr_model, the same entity the PSREF table mints); the sheet must print
           the model name (Line + Model-Gen, e.g. 'T27QD-40'), else nothing.
           (1) 'Eye Comfort ... 5-star' (TÜV Eye Comfort certified at 5 stars) -> flk.pwm none, kind derived, condition basis=certification,
               rule derive/tuv-eye-comfort-5star@1 (same rule as lenovo_monitors@4). 3/4-star or unstarred never map.
           (2) a product-feature line stating flicker-free ('Flicker-free technology', 'TÜV Rheinland Flicker Free') -> flk.pwm none, official
               (the label-mapping `flicker_free` meaning). CRT boilerplate ('do not flicker the way CRTs do') never maps; nor does any line
               that negates or qualifies ('reduced', 'low flicker').
"""
import gzip, json, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _run

ID, VERSION, SOURCE = "lenovo_datasheets", 1, "lenovo-psref-monitor-datasheets"
CATEGORIES = {"monitors"}
ADAPTER = f"{ID}@{VERSION}"
PAGES = "lenovo-psref-monitors"
BASE = "https://psrefstuff.lenovo.com/syspool/Sys/PDF/datasheet/"
DELAY = 1.0
TUV_RULE = "tuv-eye-comfort-5star@1"
TUV_REF = "https://www.certipedia.com/quality_marks/0217009904?locale=en"
FIVE = re.compile(r"Eye\s*Comfort[^\n]{0,40}?\b5[- ]?star|5[- ]?star[^\n]{0,30}?Eye\s*Comfort", re.I)
STARS_OTHER = re.compile(r"\b[1-4][- ]?star", re.I)
FF = re.compile(r"flicker[- ]?free", re.I)
NOT_CLAIM = re.compile(r"CRT|do(?:es)? not flicker|reduce[ds]?|low[- ]flicker|not\b|\bno\b", re.I)


def sheet_name(key):
    base = re.sub(r"_Monitor$", "", key)
    return re.sub(r"_([^_]+)$", r"-\1", base)


def pdf_to_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def psref_flicker(blob):
    """Does the stored PSREF table already carry a flicker fact (Flicker Free / Eye Comfort 5-star)? Then no sheet is needed."""
    t = blob.decode("utf-8", "replace")
    return bool(re.search(r"Flicker Free|Eye Comfort Certification \(5-star\)", t))


def parse_text(snap, txt):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, f"Lenovo datasheet {sheet_name(key)}")]
    model = sheet_name(key).split("_", 1)[-1]           # 'T27QD-40'
    flat = re.sub(r"\s+", " ", txt)
    if not re.search(re.escape(model).replace(r"\-", r"[- ]?"), flat, re.I):
        pr.absences.append({"key": "*", "reason": f"sheet does not print the model name {model}", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "model": model}
        return pr
    pr.identifiers.append(L.ident("mfr_model", key, "model", "lenovo", market=None))
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in txt.splitlines() if ln.strip()]
    five = [ln for ln in lines if FIVE.search(ln) and not STARS_OTHER.search(ln)]
    ff = [ln for ln in lines if FF.search(ln) and not NOT_CLAIM.search(ln)]
    if five:
        c = C.claim(key, "flk.pwm", "none", None, five[0][:300], "s1", ADAPTER, "pdf_text", snap.fetched_at,
                    {"label": "datasheet line", "derivation": TUV_RULE, "certification": "TÜV Rheinland Eye Comfort (5-star)", "rule_ref": TUV_REF},
                    five[0][:125], conditions={"basis": "certification"})
        c["kind"] = "derived"
        pr.claims.append(c)
    if ff:
        pr.claims.append(C.claim(key, "flk.pwm", "none", None, ff[0][:300], "s1", ADAPTER, "pdf_text", snap.fetched_at,
                                 {"label": "datasheet feature line"}, ff[0][:125]))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "five_star": five[:2], "flicker_free": ff[:2],
                       "flicker_lines": [ln[:120] for ln in lines if re.search(r"flicker|eye comfort|T[ÜU]V", ln, re.I)][:6]}
    return pr


class LenovoDatasheets:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ps = C.BlobStore(PAGES)
        refs, have = [], 0
        for key, s in sorted(ps.latest().items()):
            if psref_flicker(gzip.decompress(ps.read_rec(s))):
                have += 1
                continue
            refs.append(C.Ref(SOURCE, key, BASE + sheet_name(key) + "_datasheet_EN.pdf", {"psref_url": s["url"]}))
        return C.Discovery(refs, True, None, {"sheets": len(refs), "psref_has_flicker_fact": have})

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
    _run.main(LenovoDatasheets())
