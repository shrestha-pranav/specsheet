#!/usr/bin/env python3
"""ASUS (US) adapter v1, contract ARCHITECTURE 15.5.

discover : odinapi SeriesFilterResult (the list API the asus.com/us laptop finder uses), PageSize=300 -> 280 rows =
           122 series pages (www.asus.com) + 158 per-CONFIG rows (rog.asus.com; PartNo + SalesModelName like G835LXG-DB96)
           grouped into 20 ROG series pages. One Ref per distinct page URL.
fetch    : www.asus.com -> <ProductURL>techspec/  (server-rendered table, ONE COLUMN PER MODEL CODE e.g. UX5406SA, cells
                            list the CPU/panel/RAM options of that code)
           rog.asus.com -> <ProductURL>spec/      (schema.org ProductGroup JSON-LD, hasVariant[] = per-config part
                            numbers like 90NR0LI1-M00D70 with full spec properties)
parse    : pure. Identifiers: mfr_model (model code, package_level model) and mfr_sku (ROG per-config part number).
           Claims carry the source literal (list of options per cell when ASUS lists several); locator.model_code.
Not available from ASUS: per-config US retail suffix of the Zenbook/Vivobook codes (UX3405MA-PP287W); that lives on
retailer/ASUS-store listings (see research/laptops/identity.md).
"""
import html, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _run

API = ("https://odinapi.asus.com/recent-data/apiv2/SeriesFilterResult?SystemCode=asus&WebsiteCode=us&ProductLevel1Code=laptops"
       "&PageSize=300&PageIndex=1&CategoryName=&SeriesName=&SubSeriesName=&Spec=&SubSpec=&PriceMin=&PriceMax=&Sort=Recommend&siteID=www&sitelang=")
DELAY = 1.0
LABELMAP = {"Processor": "cpu.model", "Graphics": "gpu.model", "Neural Processor": "cpu.npu_tops", "Memory": "mem.size", "Storage": "stor.size",
            "Display": "disp.size", "Operating System": "sw.os", "Color": "id.color", "Weight": "phys.weight", "Dimensions (W x D x H)": "phys.dimensions",
            "Battery": "pwr.battery_wh", "Power Supply": "pwr.charger_w", "Wi-Fi": "wl.wifi", "Wireless": "wl.wifi", "Camera": "in.webcam",
            "Keyboard": "in.kb_layout", "Security": "in.tpm", "Audio": "in.speakers", "I/O Ports": "port.usbc_list", "Card Reader": "port.card_reader"}
TXT = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_table(t):
    """-> {label: [cell, ...]} where cell = list of option strings, columns aligned with the 'Model' row."""
    rows = {}
    for m in re.finditer(r'<div class="rowTableTitle">([^<]*)</div></div><div class="[^"]*rowTableItemViewBox[^"]*">(.*?)(?=<div class="[^"]*__rowTable___|$)', t, re.S):
        cells = re.findall(r'__rowTableItems___[^"]*"[^>]*>(.*?)</div>(?=<!--\]-->)', m.group(2), re.S)
        rows[TXT(m.group(1))] = [[TXT(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", c, re.S) if TXT(p)] or [TXT(c)] for c in cells]
    mm = re.search(r">Model</div>(.*?)(?=__rowTable___|$)", t, re.S)  # Model row uses a different cell markup
    if mm:
        codes = []
        for c in re.findall(r">\s*([A-Z][A-Z0-9]{3,}[A-Z0-9-]*)\s*<", mm.group(1)):
            if c not in codes:
                codes.append(c)
        if codes:
            rows["Model"] = [[c] for c in codes]
    return rows


class Asus:
    id, version, source_id, categories = "asus", 1, "asus-us", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        r = net.get(API, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return C.Discovery([], False, f"list api {getattr(r, 'status_code', r)}", checkpoint or {})
        res = r.json()["Result"]
        self.store.put(r.content, ".json")
        by_url = {}
        for p in res["ProductList"]:
            u = p["ProductURL"]
            rog = "rog.asus.com" in u
            ref = by_url.setdefault(u, {"key": p.get("PDWebPath") or u.rstrip("/").rsplit("/", 1)[1], "url": u.rstrip("/") + ("/spec/" if rog else "/techspec/"),
                                        "hints": {"title": re.sub(r"<[^>]+>", "", p["Name"]), "series": p.get("SubSeriesName") or p.get("CategoryName"),
                                                  "level2": p.get("Level2Path"), "online": p.get("ProductOnlineDt"), "rog": rog, "configs": []}})
            if p.get("PartNo"):  # ROG list rows are per-configuration: ASUS part number + retail model code (G835LXG-DB96)
                ref["hints"]["configs"].append({"part_no": p["PartNo"], "sales_model": p.get("SalesModelName"), "product_id": p.get("ProductID"),
                                                "summary": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("ModelSpec") or "")).strip()})
        refs = [C.Ref(self.source_id, v["key"], v["url"], v["hints"]) for v in by_url.values()]
        res = {"TotalCount": len(by_url), "ProductList": res["ProductList"]}
        n_rows = len(res["ProductList"])
        return C.Discovery(refs, True, None, {"list_rows": n_rows, "pages": len(refs), "rog_config_rows": sum(len(r.hints["configs"]) for r in refs)})

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        pr = C.ParseResult(sources=[{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "ASUS " + snap.ref.key}])
        obs = snap.fetched_at
        pr.aliases.append({"text": snap.ref.hints.get("title", snap.ref.key), "kind": "marketing_name"})
        codes = []
        rows = parse_table(t)
        if "Model" in rows:
            codes = [c[0] for c in rows["Model"] if c]
            for i, code in enumerate(codes):
                pr.identifiers.append({"scheme": "mfr_model", "value": code, "value_raw": code, "issuer": "asus", "market": "US",
                                       "package_level": "model", "role": "key", "sources": ["s1"]})
                for label, cells in rows.items():
                    key = LABELMAP.get(label)
                    if key and i < len(cells) and cells[i]:
                        opts = cells[i]
                        pr.claims.append(C.claim(code, key, opts if len(opts) > 1 else opts[0], None, " | ".join(opts), "s1", f"{self.id}@{self.version}",
                                                 "adapter", obs, locator={"model_code": code, "label": label}))
            pr.fingerprints["model_codes"] = len(codes)
        nvar = 0
        for cfg in snap.ref.hints.get("configs", []):  # ROG list rows (hints are cheap but come from the official list API)
            pr.identifiers.append({"scheme": "mfr_sku", "value": cfg["part_no"], "value_raw": cfg["part_no"], "issuer": "asus", "market": "US",
                                   "package_level": "configuration", "role": "key", "sources": ["s1"]})
            if cfg.get("sales_model"):
                pr.identifiers.append({"scheme": "mfr_model", "value": cfg["sales_model"], "value_raw": cfg["sales_model"], "issuer": "asus", "market": "US",
                                       "package_level": "configuration", "role": "key", "sources": ["s1"]})
            nvar += 1
        for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', t, re.S):
            try:
                j = json.loads(m.group(1))
            except ValueError:
                continue
            for j in (j if isinstance(j, list) else [j]):
                for v in j.get("hasVariant", []) if isinstance(j, dict) and j.get("@type") == "ProductGroup" else []:
                    sku = v.get("sku")
                    if not sku:
                        continue
                    nvar += 1
                    pr.identifiers.append({"scheme": "mfr_sku", "value": sku, "value_raw": sku, "issuer": "asus", "market": "US",
                                           "package_level": "configuration", "role": "key", "sources": ["s1"]})
                    for p in v.get("additionalProperty", []):
                        key = LABELMAP.get(p.get("name"))
                        if key and p.get("value"):
                            pr.claims.append(C.claim(sku, key, p["value"], None, p["value"], "s1", f"{self.id}@{self.version}", "adapter", obs,
                                                     locator={"sku": sku, "label": p["name"]}))
        pr.fingerprints["variants"] = nvar
        if not codes and not nvar:
            pr.absences.append({"key": "id.mpn", "status": "not_published", "source": "s1", "checked_at": obs})
        return pr


if __name__ == "__main__":
    _run.main(Asus())
