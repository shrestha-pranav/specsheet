#!/usr/bin/env python3
"""VESA DisplayHDR certified-products adapter v1 (contract ARCHITECTURE 15.5), category monitors (also lists some laptops/OLED notebooks).

Source   : https://displayhdr.org/certified-products/ (static WordPress HTML, robots Crawl-delay 10, one request).
Shape    : 10 <table>s, the tier is the heading text immediately before each table (DisplayHDR 400/500/600/1000/1400,
           DisplayHDR True Black 400/500/600/1000/1400); columns = Model | "Family Models: ..." | CTS version.
discover : fetch the page once (stored as blob under ref `_page`), then one Ref per (tier, model) row.
fetch    : offline: writes the row as a small JSON snapshot (final_url = the page URL; page snapshot sha in the row).
parse    : pure. mfr_model = last token of the Model cell (brand = leading text; 'ASUS ROG Swift PG32UQX' -> PG32UQX, raw kept);
           aliases = every sibling in 'Family Models' (regional/colour suffixes, OEM re-badges such as TCL/KOORUI);
           claim hdr.vesa_tier (cert is per tested model, siblings inherit only by the maker's 'family' declaration: claimed on the
           listed model, sibling claims need the matcher). cts_version in locator.
Notes    : product type (monitor vs laptop) is not stated; entity resolution decides the category.
"""
import html as H, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION, SOURCE = "displayhdr", 2, "displayhdr"
CATEGORIES = {"monitors"}
URL = "https://displayhdr.org/certified-products/"
ADAPTER = f"{ID}@{VERSION}"
PAGE_ADAPTER = f"{ID}-page@{VERSION}"   # keeps the one page snapshot out of the per-row parse set
TIER = re.compile(r"DisplayHDR\s+(True Black\s+)?(\d{3,4})\s+Certified Products?", re.I)


def txt(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<br\s*/?>", "\n", re.sub(r"<[^>]+>", " ", s.replace("<br />", "\n"))))).strip()


def parse_page(page):
    """-> [(tier, model_cell, family_cell, cts)] from the page HTML."""
    out = []
    for m in re.finditer(r"<table.*?</table>", page, re.S):
        head = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", page[max(0, m.start() - 1500):m.start()])))
        t = list(TIER.finditer(head))
        if not t:
            continue
        tier = f"DisplayHDR {'True Black ' if t[-1].group(1) else ''}{t[-1].group(2)}"
        for tr in re.findall(r"<tr>(.*?)</tr>", m.group(0), re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(tds) < 3 or txt(tds[0]) == "Model":
                continue
            fam = H.unescape(re.sub(r"<[^>]+>", "\n", tds[1].replace("<br />", "\n")))
            out.append((tier, txt(tds[0]), re.sub(r"[ \t]+", " ", fam).strip(), txt(tds[2])))
    return out


def siblings(fam):
    s = re.sub(r"^\s*Family Models?:?", "", fam.strip(), flags=re.I)
    out = []
    for tok in re.split(r"[,\n]", s):
        tok = re.sub(r"^\s*[A-Za-z][\w .&-]*:\s*", "", tok.strip())   # drop 'TCL:' style brand prefixes
        tok = tok.strip(" ;")
        if tok and not tok.endswith(":") and tok not in out:
            out.append(tok)
    return out


def model_token(cell):
    """Model number from the 'Brand Series MODEL' cell: the last whitespace token that looks like a model (3-24 chars, letter+digit,
    no brackets/quotes); else the whole cell slug capped at 40 chars (entity ids are length-limited; never a long title as the key)."""
    for tok in reversed(cell.split()):
        t = tok.strip(",;")
        if 3 <= len(t) <= 24 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/+-]*", t) and re.search(r"\d", t) and re.search(r"[A-Za-z]", t):
            return t
    return re.sub(r"[^A-Za-z0-9]+", "-", cell).strip("-")[:32]


class DisplayHdr:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        ref0 = Ref(SOURCE, "_page", URL, {})
        snap, body = C.http_snapshot(self.store, ref0, URL, 10, ".html", PAGE_ADAPTER)
        if body is None:
            return Discovery([], False, f"page {snap.status}", checkpoint or {})
        rows = parse_page(body.decode("utf-8", "replace"))
        seen, refs = set(), []
        for tier, model, fam, cts in rows:
            key = f"{tier}|{model}"
            if key in seen:
                continue
            seen.add(key)
            refs.append(Ref(SOURCE, key, URL, {"tier": tier, "model": model, "family": fam, "cts": cts, "page_snapshot": snap.snapshot}))
        by = {}
        for r in refs:
            by[r.hints["tier"]] = by.get(r.hints["tier"], 0) + 1
        return Discovery(refs, True, None, {"rows": len(rows), "refs": len(refs), "by_tier": by, "page": snap.snapshot})

    def fetch(self, ref, prior, net):
        body = json.dumps(ref.hints, sort_keys=True).encode()
        sha = self.store.put(body, ".json")
        s = C.Snapshot(sha, ref, 200, time.strftime("%FT%TZ", time.gmtime()), URL, {})
        self.store.append(s, ADAPTER, ".json")
        return s

    def parse(self, snap, blobs, profile):
        h = json.loads(blobs.read(snap.snapshot, ".json"))
        obs, cell = snap.fetched_at, h["model"]
        model = model_token(cell)
        pr = ParseResult()
        pr.sources = [{"id": "s1", "url": URL, "label": "VESA DisplayHDR certified products", "source_id": "displayhdr", "tier": "certifier",
                       "retrieved_at": obs, "snapshot": h.get("page_snapshot", snap.snapshot)}]
        pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": cell, "issuer": cell.split()[0].lower(), "market": None,
                               "package_level": "model", "role": "key", "sources": ["s1"]})
        pr.aliases.append({"text": cell, "kind": "certifier_listing", "source": "s1", "observed_at": obs})
        for sib in siblings(h.get("family", "")):
            pr.aliases.append({"text": sib, "kind": "model_variant", "source": "s1", "observed_at": obs})
        raw = f"{h['tier']} Certified Products: {cell} (CTS {h['cts']})"
        pr.claims.append(claim(model, "hdr.vesa_tier", h["tier"], None, raw, "s1", ADAPTER, "html_table", obs,
                               {"cts_version": h["cts"], "model_cell": cell}, raw))
        pr.fingerprints = {"raw": snap.snapshot, "model": model, "brand_token": cell.split()[0], "siblings": len(siblings(h.get("family", ""))), "cts": h["cts"]}
        return pr


if __name__ == "__main__":
    _run.main(DisplayHdr())
