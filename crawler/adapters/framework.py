#!/usr/bin/env python3
"""Framework (US) adapter v1, contract ARCHITECTURE 15.5.

discover : the four product landing pages https://frame.work/{laptop12,laptop13,laptop13pro,laptop16} -> every
           /products/<slug>/configuration/new link whose slug starts with laptop (DIY Edition + Pre-built; desktop/accessories skipped).
           frame.work is NOT Shopify; robots.txt: Crawl-Delay 10 (honoured: DELAY=10), /api, /products/*/tabs, /products/*/faq disallowed
           (not used). /meta_product_feeds.xml is robots-allowed but answers 401 (auth) and is not used.
fetch    : landing pages (marketing prose: weight, dimensions, battery, display, wifi) + configurator pages (1-2 MB Rails/Turbo HTML).
           Configurator embeds `data-...product-configuration-variants-data-value='[{id, sku:"FRANVW0016", option_value_ids, amount,
           availability, batch_presentation, warranty_selections...}]'` and the option radios (name=product_configuration[options][<type>],
           value=<option id>, label text = CPU / GHz / battery / display / RAM / SSD lines).
parse    : pure. configuration identifier mfr_sku = Framework SKU (FRANVW0016 = pre-built, FRAKJT0005 = DIY mainboard+module combo),
           model identifier x_framework_product = product slug (laptop13pro-intel-ultra-3, `series` = slug without -diy). Per-SKU claims
           come from the option labels the SKU is made of; landing claims attach to every product slug the landing prefixes.
           Per-port I/O: Framework ports are user-chosen Expansion Cards (4 slots; 6 on Laptop 16 + bay) - the landing sentence is claimed raw.
"""
import html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C
import _lt as L
import _run

DELAY = 10.0
BASE = "https://frame.work"
LANDINGS = ["laptop12", "laptop13", "laptop13pro", "laptop16"]
NOISE = re.compile(r"^(Pre-order|Batch \d+|Shipped|% Off|System,|Sold out|Out of stock|In stock|Ships .*|\$[\d,.]+|.*,)$")


def option_values(t):
    """{option_value_id: (type, [label lines])} from the configurator radios."""
    out = {}
    for p in re.split(r'(?=<input type="radio" name="product_configuration\[options\]\[)', t)[1:]:
        m = re.match(r'<input type="radio" name="product_configuration\[options\]\[([^\]]+)\]"[^>]*value="(\d+)"[^>]*>', p)
        if not m:
            continue
        seg = p[m.end():]
        seg = seg[:seg.find("</label>")] if "</label>" in seg else seg[:3000]
        seg = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", seg, flags=re.S)
        ls = [l for l in L.lines(re.sub(r"</(span|div|p)>", "</\\1>\n", seg)) if not NOISE.match(l) and not l.startswith("Batch")]
        out[int(m.group(2))] = (m.group(1), ls)
    return out


def classify(typ, ls):
    """option label lines -> [(key, value, raw)]"""
    if not ls:
        return []
    res = []
    if typ == "processor":
        res.append(("cpu.model", ls[0], ls[:1]))
        for l in ls[1:]:
            if re.search(r"\d+Wh", l):
                res.append(("pwr.battery_wh", l, [l]))
            elif re.search(r"Display|Touchscreen|nit", l):
                res.append(("disp.size", l, [l]))
            elif re.search(r"LPDDR|DDR\d|Memory", l):
                res.append(("mem.size", l, [l]))
            elif re.search(r"NVMe|SSD|Storage", l):
                res.append(("stor.size", l, [l]))
            elif re.search(r"core", l) and "GHz" not in l:
                res.append(("cpu.cores_threads", l, [l]))
            elif re.search(r"GHz", l):
                res.append(("cpu.boost_clock", l, [l]))
                if re.search(r"core", l):
                    res.append(("cpu.cores_threads", l, [l]))
    elif typ == "operating-system":
        res.append(("sw.os", ls[0], ls))
    elif typ == "keyboard":
        res.append(("in.kb_layout", ls[0], ls[:1]))
    elif typ.lower().startswith("touchpad"):
        res.append(("input.touchpad", ls[0], ls[:1]))
    elif typ == "expansion-bay-module" and re.search(r"Graphics Module", ls[0]):
        res.append(("gpu.model", ls[0], ls[:1]))
    return res


class Framework:
    id, version, source_id, categories = "framework", 1, "framework-us", {"laptops"}

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        cfg, refs = {}, []
        for lp in LANDINGS:
            r = net.get(f"{BASE}/{lp}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery([], False, f"{lp} -> {getattr(r, 'status_code', r)}", checkpoint or {})
            for s in re.findall(r'href="/products/(laptop[a-z0-9-]*)/configuration/new"', r.text):
                cfg[s] = f"{BASE}/products/{s}/configuration/new"
        for lp in LANDINGS:
            targets = sorted(s for s in cfg if s.startswith(lp + "-"))
            refs.append(C.Ref(self.source_id, f"landing:{lp}", f"{BASE}/{lp}", {"kind": "landing", "targets": targets}))
        for s, u in sorted(cfg.items()):
            refs.append(C.Ref(self.source_id, f"config:{s}", u, {"kind": "configure", "slug": s, "edition": "DIY" if "-diy-" in s else "Pre-built"}))
        return C.Discovery(refs, True, None, {"products": sorted(cfg)})

    def fetch(self, ref, prior, net):
        snap, _ = C.http_snapshot(self.store, ref, ref.url, DELAY, ".html", f"{self.id}@{self.version}")
        return snap

    def parse(self, snap, blobs, profile):
        t = blobs.read(snap.snapshot, ".html").decode("utf-8", "replace")
        pr = C.ParseResult(sources=[L.source(snap, "Framework " + snap.ref.key)])
        title = re.search(r"<title>(.*?)</title>", t, re.S)
        kind = snap.ref.hints.get("kind") or snap.ref.key.split(":")[0].replace("config", "configure")
        pr.aliases.append({"text": html.unescape(title.group(1)).strip() if title else snap.ref.key, "kind": "marketing_name"})
        return (self._configure if kind == "configure" else self._landing)(t, snap, pr)

    def _configure(self, t, snap, pr):
        a = f"{self.id}@{self.version}"
        slug = snap.ref.hints.get("slug") or snap.ref.key.split(":", 1)[1]
        series = slug.replace("-diy", "")
        pr.identifiers.append(L.ident("x_framework_product", slug, "model", "framework", series=series))
        m = re.search(r"product-configuration-variants-data-value='(.*?)'\s", t, re.S)
        if not m:
            pr.absences.append({"key": "id.mpn", "status": "not_published", "source": "s1", "checked_at": snap.fetched_at})
            return pr
        variants = json.loads(html.unescape(m.group(1)))
        opts = option_values(t)
        pr.fingerprints["edition"] = snap.ref.hints.get("edition")
        pr.fingerprints["option_types"] = sorted({v[0] for v in opts.values()})
        for v in variants:
            sku = v["sku"]
            pr.identifiers.append(L.ident("mfr_sku", sku, "configuration", "framework", parent=slug))
            for oid in v.get("option_value_ids", []):
                typ, ls = opts.get(oid, (None, []))
                for key, value, raw in classify(typ or "", ls):
                    L.add(pr, a, snap, key, value, raw, "sku", sku, f"option:{typ}")
            if v.get("amount"):
                L.add(pr, a, snap, "sw.msrp", f"{v['amount']} USD", f"configurator price {v['amount']} USD ({v.get('availability')}, {v.get('batch_presentation')}) at fetch", "sku", sku, "variant.amount")
            if v.get("warranty_selections"):
                L.add(pr, a, snap, "sw.warranty", [w["display_text"] for w in v["warranty_selections"]], [w["display_text"] for w in v["warranty_selections"]], "sku", sku, "variant.warranty_selections")
        pr.fingerprints["variants"] = len(variants)
        return pr

    def _landing(self, t, snap, pr):
        a = f"{self.id}@{self.version}"
        x = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
        x = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", x)))
        x = re.sub(r"(\| ?)+", "|", x)
        facts = {}
        for dim in ("Width", "Depth", "Height"):
            m = re.search(r"([\d.]+ ?mm)\|[^|]*\|" + dim + r"\|", x)
            if m:
                facts[dim] = m.group(1)
        m = re.search(r"([\d.]+ ?kg)\|[^|]*\|Weight\|", x)
        weight = m.group(1) if m else None
        para = {}
        for lab in ("Display", "Battery", "Networking", "Speakers", "Keyboard"):
            m = re.search(r"\|" + lab + r" ?\|([^|]{20,400})\|", x)
            if m:
                para[lab] = m.group(1).strip()
        m = re.search(r"\|([^|]*Expansion Cards?[^|]{0,300})\|", x)
        ports = m.group(1).strip() if m else None
        targets = snap.ref.hints.get("targets") or []
        for tgt in targets:
            if facts:
                L.add(pr, a, snap, "phys.dimensions", [f"{k}: {v}" for k, v in facts.items()], [f"{k}: {v}" for k, v in facts.items()], "model_code", tgt, "landing:dimensions", entity=tgt)
            L.add(pr, a, snap, "phys.weight", weight, weight or "", "model_code", tgt, "landing:weight", entity=tgt)
            for lab, key in (("Display", "disp.size"), ("Battery", "pwr.battery_wh"), ("Networking", "wl.wifi"), ("Speakers", "in.speakers"), ("Keyboard", "in.kb_layout")):
                if lab in para:
                    L.add(pr, a, snap, key, para[lab], para[lab], "model_code", tgt, "landing:" + lab, entity=tgt)
            L.add(pr, a, snap, "port.usbc_list", ports, ports or "", "model_code", tgt, "landing:expansion cards", entity=tgt)
        for tgt in targets:
            pr.identifiers.append(L.ident("x_framework_product", tgt, "model", "framework", series=tgt.replace("-diy", "")))
        pr.fingerprints["landing_facts"] = {"dims": facts, "weight": weight, "paragraphs": sorted(para), "ports": bool(ports)}
        return pr


if __name__ == "__main__":
    _run.main(Framework())
