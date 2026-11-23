#!/usr/bin/env python3
"""CyberPower adapter, contract v1 (ARCHITECTURE.md 15.5). Source = WordPress REST API of cyberpowersystems.com.

discover : /wp-json/wp/v2/product?per_page=100&product_cat=<id> for the consumer surge / strip / power-center categories
           (list pages are snapshotted; acf.product_specs carries the full spec table as HTML, acf.highlights the bullets).
fetch    : the per-product item JSON is a canonical re-serialisation of the list item (feed blob, no extra request).
resources: acf.resources_literature -> /wp-json/wp/v2/resources?include=... (slug suffix -DS = datasheet, -UM manual,
           -WS web sheet); the PDF URL sits in content.rendered (images.salsify.com). Datasheets are downloaded (blob).
parse    : pure over the item blob: identifiers, alias, claims from product_specs, absences.
Usage    : python3 -I crawler/adapters/cyberpower.py discover|fetch|parse|run|docs   (generic runner _run.py; parse is offline;
           `docs` downloads the linked -DS datasheet PDFs through the shared client)
Class-style adapter (round 3): CyberPower.discover/fetch/parse(snap, blobs, profile); parse_item() is the pure parser.
"""
import html, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, Snapshot, ParseResult, claim, http_snapshot  # noqa
import _run

ID, VERSION, SOURCE = "cyberpower", 1, "cyberpower"
CATEGORIES = {"power-strips"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.cyberpowersystems.com/wp-json/wp/v2"
# product_cat ids: 167 children = surge (essential 168, home-office 201, advanced 2344, hospital 4714, GX 6787, multi-pack 6966);
# general-power 239 children = power strips 245, desktop 240, adapters/taps 346, extension cords 349, multi-packs 2505, hospital 6728.
# 213 rackbar (rack surge strips). Excluded: 154 PDUs (metered/monitored), 6967 portable power stations, inverters, UPS.
CATS = {168: "surge-essential", 201: "surge-home-office", 2344: "surge-advanced", 4714: "surge-hospital", 6787: "surge-gx",
        6966: "surge-multipack", 245: "power-strips", 240: "desktop-power", 346: "adapters-taps", 349: "extension-cords",
        2505: "gp-multipacks", 6728: "gp-hospital", 213: "rackbar"}
DISCONTINUED = 1539
FIELDS = "id,slug,link,title,modified,product_cat,acf"


def _json(b):
    return json.loads(b)


def _discover(checkpoint, store, cats=CATS):
    items, complete, stop = {}, True, None
    for cid, cname in cats.items():
        page = 1
        while True:
            url = f"{BASE}/product?per_page=100&page={page}&product_cat={cid}&_fields={FIELDS}"
            ref = Ref(SOURCE, f"list-{cid}-{page}", url)
            snap, body = http_snapshot(store, ref, url, 1.0, ".json", ADAPTER)
            if body is None:
                if snap.status == 400 and page > 1:     # WP: page past the end
                    break
                complete, stop = False, f"cat {cid} page {page} status {snap.status}"
                break
            data = _json(body)
            for it in data:
                e = items.setdefault(it["id"], dict(it, _cats=[]))
                e["_cats"].append(cname)
            if len(data) < 100:
                break
            page += 1
    refs = []
    for pid, it in sorted(items.items()):
        model = (it.get("acf") or {}).get("model") or it["title"]["rendered"]
        refs.append(Ref(SOURCE, str(pid), it["link"], {"title": html.unescape(it["title"]["rendered"]), "skus": [model], "cats": it["_cats"],
                                                        "discontinued": DISCONTINUED in it["product_cat"], "item": it}))
    return Discovery(refs, complete, stop, {"products": len(refs)})


def _fetch(ref, store):
    item = {k: v for k, v in ref.hints["item"].items() if not k.startswith("_")}
    body = json.dumps(item, sort_keys=True, ensure_ascii=False).encode()
    sha = store.put(body, ".json")
    snap = Snapshot(sha, Ref(ref.source_id, ref.key, ref.url, {"cats": ref.hints["cats"]}), 200, time.strftime("%FT%TZ", time.gmtime()), ref.url, {})
    store.append(snap, ADAPTER, ".json")
    return snap


def fetch_resources(store, ids):
    """ids -> {id: {slug, pdf}} through batched REST calls (snapshotted)."""
    out, ids = {}, sorted(set(ids))
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        url = f"{BASE}/resources?per_page=40&include={','.join(map(str, chunk))}&_fields=id,slug,title,content"
        snap, body = http_snapshot(store, Ref(SOURCE, f"res-{chunk[0]}", url), url, 1.0, ".json", ADAPTER)
        for r in (_json(body) if body else []):
            m = re.search(r'https?://[^"\']+\.pdf', r["content"]["rendered"])
            out[r["id"]] = {"slug": r["slug"], "pdf": m.group(0) if m else None}
    return out


# ------------------------------------------------------------------ parse (pure)
def spec_rows(htm):
    """product_specs HTML -> [(section, label, value)]"""
    rows, sec = [], None
    for tr in re.findall(r"<tr>(.*?)</tr>", htm or "", re.S):
        th = re.search(r"<th[^>]*>(.*?)</th>", tr, re.S)
        if th:
            sec = html.unescape(re.sub(r"<[^>]+>", "", th.group(1))).strip(); continue
        td = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(td) == 2:
            clean = lambda x: html.unescape(re.sub(r"\s+", " ", re.sub(r"<br\s*/?>", "; ", x)).replace("<", "<")).strip()
            rows.append((sec, clean(re.sub(r"<[^>]+>(?!;)", "", td[0])), re.sub(r"<[^>]+>", "", clean(td[1]))))
    return rows


def num(s):
    m = re.search(r"-?\d[\d,]*\.?\d*", s or "")
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    return int(v) if v == int(v) else v


def yn(s):
    s = (s or "").strip().lower()
    return True if s.startswith("yes") else False if s.startswith("no") else None


def cord_ft(s):
    m = re.match(r"\s*([\d.]+)\s*ft", s or "")
    return (int(float(m.group(1))) if float(m.group(1)) == int(float(m.group(1))) else float(m.group(1))) if m else None


MAP = {  # label -> (key, unit, fn)
    "Surge Suppression (Joules)": ("surge.joules", "J", num),
    "Maximum Surge Current": ("surge.max_surge_current", "A", num),
    "Cord Length": ("cord.length_ft", "ft", cord_ft),
    "Input Plug Type": ("cord.plug_type", None, lambda s: s.strip()),
    "Nominal Input Voltage": ("load.voltage", "V", num),
    "Maximum Input Current": ("load.max_amps", "A", num),   # "Amperage" row has data errors ("125 A"), left unmapped
    "Outlets - Total": ("outlets.count", None, num),
    "USB Charge Port Quantity": ("usb.ports", None, num),
    "USB Charge Port Watts": ("usb.total_w", "W", num),
    "Material of Construction": ("phys.material", None, lambda s: s.strip()),
    "Response Time": ("surge.response_time", None, lambda s: s.strip()),
    "Clamping Voltage": ("surge.vpr_max", "V", lambda s: max(map(int, re.findall(r"(\d+)\s*V", s))) if re.search(r"\d+\s*V", s) else None),
    "Auto Shutoff": ("safety.auto_shutoff", None, yn),
    "Right Angle Outlets": ("outlets.right_angle", None, yn),
    "Rotating Outlets": ("outlets.rotating", None, yn),
}


def parse_item(item, ref, snap_sha, observed, resources=None):
    pr = ParseResult()
    acf = item.get("acf") or {}
    model = (acf.get("model") or item["title"]["rendered"]).strip()
    pr.sources = [{"id": "s1", "url": item["link"], "label": "CyberPower product page (WP REST item)", "source_id": "cyberpower-rest",
                   "tier": "manufacturer", "retrieved_at": observed, "snapshot": snap_sha}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model.upper(), "value_raw": model, "issuer": "cyberpower", "market": "US"})
    for t, k in ((acf.get("heading"), "marketing_name"), (acf.get("title_caption"), "marketing_name")):
        if t and t.strip():
            pr.aliases.append({"text": html.unescape(t.strip()), "kind": k, "source": "s1", "observed_at": observed})
    rows = spec_rows(acf.get("product_specs"))
    seen, unmapped = set(), {}
    for sec, label, raw in rows:
        if label in MAP:
            key, unit, fn = MAP[label]
            v = fn(raw)
            if v is None or key in seen:
                unmapped.setdefault(label, raw); continue
            seen.add(key)
            pr.claims.append(claim(model, key, v, unit, raw, "s1", ADAPTER, "table", observed, {"table": "product_specs", "section": sec, "label": label}, f"{label}: {raw}"))
        elif label in ("Certifications", "Safety") or "Agency" in label:
            ed = re.search(r"UL ?1449\s+(\d)(?:st|nd|rd|th)\s+Edition", raw)
            if ed:
                pr.claims.append(claim(model, "type.ul1449_edition", f"{ed.group(1)}{'th' if ed.group(1) not in '123' else {'1':'st','2':'nd','3':'rd'}[ed.group(1)]}", None, raw, "s1", ADAPTER, "table", observed, {"table": "product_specs", "label": label}, f"{label}: {raw}"))
            for key, rx in (("type.ul1449_listed", r"UL ?1449"), ("type.ul1363_listed", r"UL ?1363")):
                if re.search(rx, raw):
                    pr.claims.append(claim(model, key, True, None, raw, "s1", ADAPTER, "table", observed, {"table": "product_specs", "label": label}, f"{label}: {raw}"))
            unmapped.setdefault(label, raw)
        else:
            unmapped.setdefault(label, raw)
    dl, dl_raw = [], []                                           # one list claim from the three protection rows (`surge.dataline`)
    for label, item in (("Phone Protection RJ11", "phone_dsl"), ("Coax Protection RG6", "coax"), ("Network Protection RJ45", "ethernet")):
        if label in unmapped:
            raw = unmapped.pop(label)
            dl_raw.append(f"{label}: {raw}")
            if raw.strip().lower() not in ("", "none", "no", "n/a"):
                dl.append(item)
    if dl_raw:
        pr.claims.append(claim(model, "surge.dataline", sorted(dl), None, "; ".join(dl_raw), "s1", ADAPTER, "table", observed,
                               {"table": "product_specs", "labels": [r.split(":")[0] for r in dl_raw]}, "; ".join(dl_raw)))
    for key, why in (("surge.joules", "no joule rating row in product_specs (plain strip or incomplete listing)"),):
        if key not in seen:
            pr.absences.append({"key": key, "reason": why, "source": "s1"})
    lit = acf.get("resources_literature") or ""
    ids = [int(x) for x in re.findall(r"\d+", lit if isinstance(lit, str) else json.dumps(lit))]
    for rid in ids:
        r = (resources or {}).get(rid)
        if r and r["pdf"]:
            kind = "datasheet" if r["slug"].endswith("-ds") else "manual" if r["slug"].endswith("-um") else "other"
            pr.documents.append({"url": r["pdf"], "kind": kind, "label": r["slug"]})
            pr.links.append(Ref(SOURCE, r["slug"], r["pdf"], {"kind": kind}))
    pr.fingerprints = {"raw": snap_sha, "spec_section": sorted(l for _, l, _ in rows), "unmapped": unmapped, "highlights": bool(acf.get("highlights")),
                       "model": model, "cats": ref.hints.get("cats")}
    return pr


# ------------------------------------------------------------------ adapter (class style, runner _run.py)
class CyberPower:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        d = _discover(checkpoint, self.store)
        ids = set()
        for ref in d.refs:
            lit = (ref.hints["item"].get("acf") or {}).get("resources_literature") or ""
            ids |= {int(x) for x in re.findall(r"\d+", lit if isinstance(lit, str) else json.dumps(lit))}
        res = fetch_resources(self.store, ids)
        (self.store.dir / "resources.json").write_text(json.dumps(res))
        return d

    def fetch(self, ref, prior, net):
        return _fetch(ref, self.store)       # item JSON is a re-serialisation of the list item: no request

    def wants(self, rec):
        """_run hook: the log also holds list pages, resource batches and datasheet PDFs; only item JSON is an entity."""
        return rec["ref"].isdigit() and rec["blob"].endswith(".json")

    def parse(self, snap, blobs, profile):
        res = {int(k): v for k, v in json.loads((blobs.dir / "resources.json").read_text()).items()}
        return parse_item(_json(blobs.read(snap.snapshot, ".json")), snap.ref, snap.snapshot, snap.fetched_at, res)

    def fetch_datasheets(self):
        n = 0
        got = {x["url"] for x in self.store.snapshots() if x["status"] == 200 and x["blob"].endswith(".pdf")}
        for p in sorted((self.store.dir / "parsed").glob("*.json")):
            for l in json.loads(p.read_text())["links"]:
                if l["hints"].get("kind") == "datasheet" and l["url"] not in got:
                    got.add(l["url"])
                    snap, b = http_snapshot(self.store, Ref(**l), l["url"], 1.0, ".pdf", ADAPTER)
                    n += b is not None
        print(f"datasheets downloaded {n}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["docs"]:
        CyberPower().fetch_datasheets()
    else:
        _run.main(CyberPower())
