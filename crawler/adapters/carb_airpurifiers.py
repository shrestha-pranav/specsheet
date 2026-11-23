#!/usr/bin/env python3
"""CARB certified air cleaning devices adapter v1 (contract ARCHITECTURE 15.5), category air-purifiers. Ozone/certification source.

Source   : https://ww2.arb.ca.gov/list-carb-certified-air-cleaning-devices (California Air Resources Board; one server-rendered table,
           ~13,000 rows: Brand | Model Name | Model Number | Type | Date Notified | EO Number). robots.txt `User-agent: *`: Crawl-delay 5,
           Disallow /*? (no query strings): ONE plain GET per run, no query string.
discover : that one GET (ref '_list'). Rows grouped per (canonical brand, normalised model). A group becomes a ref only when
           (a) its brand is in MINT_BRANDS (major US purifier makers; certification date >= MINT_SINCE), or
           (b) the exact (brand, model) already exists in the ENERGY STAR or a maker-site discovery (exact normalised string, no stem, no
               wildcard expansion: certification is attached only to an exactly named model).
           Rows whose Model Name names another appliance (hand dryer, air conditioner, HVAC/duct, ...) and model cells holding several
           numbers ('A, B') are dropped and counted, never split or guessed.
fetch    : no network; a snapshot record per ref pointing at the '_list' blob.
parse    : pure. ozone.carb_certified=True (affirmative, dated: quote names EO number + date notified), ozone.carb_type (Mechanical /
           Electronic as listed; two rows that disagree -> unresolved), ozone.carb_date (earliest ISO date notified), ozone.carb_eo.
           Absence from the list is unknown, never false (the list is current certifications; unlisted can mean not sold in California).
"""
import html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _airpurifier as A
import _run

ID, VERSION, SOURCE = "carb_airpurifiers", 1, "carb-airpurifiers"
CATEGORIES = {"air-purifiers"}
URL = "https://ww2.arb.ca.gov/list-carb-certified-air-cleaning-devices"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 5.0
LIST = "_list"
MINT_SINCE = "2019-01-01"
MINT_BRANDS = {"coway", "levoit", "winix", "honeywell", "blueair", "dyson", "shark", "lg", "samsung", "airdoctor", "dreo", "medify",
               "molekule", "alen", "iqair", "rabbit air", "germguardian", "sharp", "bissell", "mila", "hathaspace", "philips", "vornado"}
TYPE = {"mechanical": "mechanical", "mechanica1": "mechanical", "electronic": "electronic", "elecronic": "electronic"}
PEERS = ("energystar-airpurifiers", "levoit-us-airpurifiers", "winix-us-airpurifiers")
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def table(body):
    out = []
    for r in ROW.findall(body):
        c = [A.clean(x) for x in CELL.findall(r)]
        if len(c) == 6:
            out.append(dict(zip(("brand", "name", "model", "type", "date", "eo"), c)))
    return out


def model_cell(m):
    """-> cleaned single model string, or None when the cell is empty / lists several numbers."""
    m = re.sub(r"[,;.\s]+$", "", (m or "").strip())
    if not m or re.search(r"[,;]|\s/\s|\s&\s|\band\b", m):
        return None
    return m if A.model_ok(m) else None


def peer_keys(root=None):
    keys = set()
    for sid in PEERS:
        p = Path(root or C.ROOT) / "raw" / sid / "discovery.json"
        if p.exists():
            for r in json.loads(p.read_text()).get("refs", []):
                h = r.get("hints") or {}
                if h.get("brand") and h.get("model") and not h.get("wildcard"):
                    keys.add(f"{h['brand']}|{A.norm(h['model'])}")
    return keys


def group(rows, peers):
    groups, st = {}, {"rows": len(rows), "not_purifier": 0, "multi_or_bad_model": 0}
    for r in rows:
        if A.NOT_PURIFIER.search(r["name"]):
            st["not_purifier"] += 1
            continue
        m = model_cell(r["model"])
        if m is None:
            st["multi_or_bad_model"] += 1
            continue
        b = A.brand_id(r["brand"])
        k = f"{b}|{A.norm(m)}"
        groups.setdefault(k, {"brand": b, "model": m, "rows": []})["rows"].append(r)
    refs = {}
    for k, g in groups.items():
        dates = [r["date"] for r in g["rows"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"])]
        mint = g["brand"] in A.BRAND_NAMES and g["brand"] in MINT_BRANDS and dates and max(dates) >= MINT_SINCE
        if mint or k in peers:
            refs[k] = {"brand": g["brand"], "model": g["model"], "eo": sorted({r["eo"] for r in g["rows"]}), "via": "brand" if mint else "exact_peer"}
    st["groups"], st["refs"] = len(groups), len(refs)
    st["refs_exact_peer"] = sum(1 for v in refs.values() if v["via"] == "exact_peer")
    return refs, st


class CarbAirPurifiers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        snap, body = C.http_snapshot(self.store, Ref(SOURCE, LIST, URL, {}), URL, DELAY, ".html", ADAPTER)
        if body is None:
            return Discovery([], False, f"list {snap.status}", checkpoint or {})
        refs, st = group(table(body.decode("utf-8", "replace")), peer_keys())
        return Discovery([Ref(SOURCE, k, URL, h) for k, h in sorted(refs.items())], True, None, st)

    def fetch(self, ref, prior, net):
        return A.shared_list_snapshot(self.store, ref, LIST, ADAPTER, ".html")

    def parse(self, snap, blobs, profile):
        h = snap.ref.hints or {}
        if snap.ref.key == LIST or not h.get("model"):
            pr = ParseResult()
            pr.absences.append({"key": "*", "reason": "CARB list snapshot (per-model refs carry the claims)", "source": "s1"})
            return pr
        rows = _rows(blobs, snap.snapshot)
        mine = [r for r in rows if A.brand_id(r["brand"]) == h["brand"] and model_cell(r["model"]) and A.norm(model_cell(r["model"])) == A.norm(h["model"])
                and not A.NOT_PURIFIER.search(r["name"])]
        return parse_rows(snap, h, mine)


_CACHE = {}


def _rows(blobs, sha):
    if sha not in _CACHE:
        _CACHE.clear()
        _CACHE[sha] = table(blobs.read(sha, ".html").decode("utf-8", "replace"))
    return _CACHE[sha]


def parse_rows(snap, h, rows):
    pr, obs = ParseResult(), snap.fetched_at
    model = h["model"]
    if not rows:
        pr.absences.append({"key": "*", "reason": "model no longer on the CARB list snapshot", "source": "s1"})
        return pr
    pr.sources = [{"id": "s1", "url": URL, "label": "CARB list of certified air cleaning devices", "source_id": SOURCE, "tier": "regulatory",
                   "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": rows[0]["model"], "issuer": h["brand"], "market": "US",
                           "package_level": "model", "role": "key", "sources": ["s1"]})
    names = sorted({r["name"] for r in rows if r["name"] and r["name"].lower() not in ("air purifier", "air cleaner")})
    for n in names[:3]:
        pr.aliases.append({"text": n[:80], "kind": "certifier_listing", "source": "s1", "observed_at": obs})
    rows = sorted(rows, key=lambda r: (r["date"], r["eo"]))
    eos = sorted({r["eo"] for r in rows if r["eo"]})
    lit = "; ".join(f"{r['brand']} | {r['name']} | {r['model']} | {r['type']} | {r['date']} | {r['eo']}" for r in rows)[:300]
    loc = {"eo_number": ",".join(eos), "date_notified": ",".join(sorted({r["date"] for r in rows}))}
    pr.claims.append(claim(model, "ozone.carb_certified", True, None, lit, "s1", ADAPTER, "html_table", obs, dict(loc),
                           f"CARB certified air cleaning device, EO {', '.join(eos)}, notified {rows[0]['date']}"))
    types = {TYPE.get(r["type"].strip().lower()) for r in rows}
    if len(types) == 1 and None not in types:
        pr.claims.append(claim(model, "ozone.carb_type", types.pop(), None, lit, "s1", ADAPTER, "html_table", obs, dict(loc), lit))
    else:
        pr.claims.append(claim(model, "ozone.carb_type", None, None, lit, "s1", ADAPTER, "html_table", obs, dict(loc), lit, status="unknown"))
    iso = sorted(r["date"] for r in rows if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]))
    if iso:
        pr.claims.append(claim(model, "ozone.carb_date", iso[0], None, lit, "s1", ADAPTER, "html_table", obs, dict(loc), lit))
    if eos:
        pr.claims.append(claim(model, "ozone.carb_eo", ", ".join(eos), None, lit, "s1", ADAPTER, "html_table", obs, dict(loc), lit))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "rows": len(rows), "via": h.get("via")}
    return pr


if __name__ == "__main__":
    _run.main(CarbAirPurifiers())
