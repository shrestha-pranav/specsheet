#!/usr/bin/env python3
"""iRobot US robot-vacuum adapter v2 (contract ARCHITECTURE 15.5), category robot-vacuums. Source = www.irobot.com (Salesforce Commerce Cloud, SFRA).
v2: fingerprints.unmapped is a {label: example} map (v1 wrote a list, which import.py cannot read); claims unchanged.

discover : the product grid XHR the category page itself calls for 'load more':
           /on/demandware.store/Sites-iRobotUS-Site/en_US/Search-UpdateGrid?cgid=us-products-plp&...&start=N&sz=24 (public HTML fragment; robots
           only disallows '*/search?'). Tiles link /en_US/<slug>/<PID>.html; robot units have a real iRobot model code as PID (X285020, C975020).
           Kept: PIDs [A-Z]\\d{6} whose slug names a Roomba robot (the Electro+ hard-floor cleaner, accessories, kits are dropped). PIDs sharing a slug
           are colour variants of one product (X285020 black / X285220 white) -> one model.
fetch    : bundle = Product-Variation?pid=<PID>&quantity=1 for every member PID: the JSON the PDP uses on variant change (product.productName,
           product.upc, product._gtmMasterID, variationAttributes, and top-level pdpSpecs = the 'Specifications' HTML of the PDP).
parse    : pure. pdpSpecs 'Details' <li> rows 'Robot Weight (lbs): 12.787', 'Robot Dimensions (in): 14.7 (L) x 14.4 (W) x 4.1 (H)',
           'AutoWash Dock Dimensions (in): ...', 'Battery Type: 6000 mAH, LFP'; the unit sits in the label. 'Retail box' rows are not read.
Identity : mfr_model = the iRobot model code (PID) of the canonical (first) variant; other colour PIDs are configuration mfr_sku aliases
           (option = colour) and the UPC a gtin alias. The marketing name (Roomba Max 775 Combo Robot + AutoWash Dock) is an alias.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _robovac as RV
import _run

ID, VERSION, SOURCE = "irobot_robovac", 3, "irobot-us-robovac"     # v3: review-3 plausibility rejections kept as preview
CATEGORIES = {"robot-vacuums"}
ADAPTER = f"{ID}@{VERSION}"
BASE = "https://www.irobot.com"
GRID = (BASE + "/on/demandware.store/Sites-iRobotUS-Site/en_US/Search-UpdateGrid?cgid=us-products-plp&prefn1=country&prefn2=ooboRestricted"
        "&prefv1=us&prefv2=false&srule=best-matches&start={}&sz=24")
VAR = BASE + "/on/demandware.store/Sites-iRobotUS-Site/en_US/Product-Variation?pid={}&quantity=1"
TILE = re.compile(r'/en_US/([a-z0-9%_.-]+)/([A-Z]\d{6})\.html')


def is_robot_slug(slug):
    return "roomba" in slug and not re.search(r"electro|refill|kit|replenish|brush|filter|bag|pad|battery|dock-only|accessor", slug)


class IrobotRobovac:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        slugs, stop, tiles = {}, None, 0
        for page in range(20):
            r = net.get(GRID.format(page * 24), RV.DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                stop = f"grid start={page * 24}: {getattr(r, 'status_code', r)}"
                break
            found = set(TILE.findall(r.text))
            if not found:
                break
            tiles += len(found)
            for slug, pid in found:
                if is_robot_slug(slug):
                    slugs.setdefault(slug, set()).add(pid)
        else:
            stop = "page cap"
        refs = []
        for slug, pids in sorted(slugs.items()):
            pids = sorted(pids)
            refs.append(C.Ref(SOURCE, pids[0].lower(), f"{BASE}/en_US/{slug}/{pids[0]}.html", {"slug": slug, "pids": pids}))
        return C.Discovery(refs, stop is None, stop, {"tiles": tiles, "models": len(refs)})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        out, missing = {}, []
        for pid in ref.hints.get("pids") or [ref.key.upper()]:
            r = net.get(VAR.format(pid), RV.DELAY)
            if hasattr(r, "status_code") and r.status_code == 200:
                try:
                    out[pid] = r.json()
                    continue
                except ValueError:
                    pass
            missing.append(pid)
        if not out:
            s = C.Snapshot("sha256:", ref, "no variation JSON", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json.gz")
            return s
        blob = gzip.compress(json.dumps({"page_url": ref.url, "variations": out, "missing": missing}, sort_keys=True).encode(), 6, mtime=0)
        s = C.Snapshot(self.store.put(blob, ".json.gz"), ref, 200, now, VAR.format(sorted(out)[0]), {"etag": None, "last_modified": None})
        self.store.append(s, ADAPTER, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, RV.read_bundle(blobs, snap))


def spec_rows(h):
    """'Details' list items -> [(label, unit_from_label, value)]. pdpSpecs is <p><b>header</b></p><ul>..</ul> sections in either order
    ('Details' then "What's in the box?", or the reverse): only the section headed 'Details' is read."""
    parts = re.split(r"(?i)<p[^>]*>\s*<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>\s*:?\s*</p>", h or "")
    h = next((parts[i + 1] for i in range(1, len(parts) - 1, 2) if re.search(r"(?i)\b(details|specifications)\b", RV.text(parts[i]))), "")
    h = re.sub(r"(?i)<br\s*/?>", "</p><p>", h)
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>|<p[^>]*>(.*?)</p>", h, re.S):
        li = li[0] or li[1]
        t = RV.text(li).replace("™", "").replace("®", "")
        m = re.match(r"(.+?)(?:\s*\(([^)]*)\))?\s*:?\s*(\d.*)$", t)
        if m and not re.search(r"\d", m[1]):
            out.append((m[1].strip(" :"), (m[2] or "").strip().lower(), m[3].strip()))
    return out


def dims_in(v, unit, robot=False):
    """'14.7 (L) x 14.4 (W) x 4.1 (H)' / '15.8 (W) x 16.4 (D) x 16.3 (H)' with the label unit 'in' / 'mm' / 'cm' -> {length,width,height} mm.
    Axis markers decide the mapping (L or D = length). Unmarked triples ('3.4 x 13.3 x 13.3', '14.1 x 13.8 x 4.2'): only for the robot body,
    whose height is by construction its smallest axis (plausible_robot bounds it); unmarked dock triples are not read."""
    f = {"in": 25.4, "inches": 25.4, "mm": 1, "cm": 10}.get(unit)
    m = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\(\s*([LWDH])\s*\)?)?", v)
    if len(m) != 3 or not f or not re.search(r"[x×]", v):
        return None
    vals = [round(float(x) * f, 1) for x, _ in m]
    axes = [a for _, a in m]
    if all(axes) and len(set(a.replace("D", "L") for a in axes)) == 3:
        d = {{"L": "length", "D": "length", "W": "width", "H": "height"}[a]: x for a, x in zip(axes, vals)}
        return {"length": d["length"], "width": d["width"], "height": d["height"]}
    if any(axes) or not robot:
        return None
    h = min(vals)
    rest = list(vals)
    rest.remove(h)
    return {"length": rest[0], "width": rest[1], "height": h}


def weight(v, unit):
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(lbs?|kg)?\.?\s*", v, re.I)
    if not m:
        return None
    u = (m[2] or unit or "").lower()
    return round(float(m[1]) * 453.592) if u.startswith("lb") else round(float(m[1]) * 1000) if u == "kg" else None


def parse_bundle(snap, b):
    pr = C.ParseResult()
    pr.sources = [{"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": "iRobot US product data " + snap.ref.key.upper()}]
    var = b.get("variations") or {}
    if not var:
        pr.absences.append({"key": "*", "reason": "no Product-Variation JSON in bundle", "source": "s1"})
        return pr
    code = sorted(var)[0]
    d = var[code]
    p = d.get("product") or {}
    name = RV.text(p.get("productName") or "").replace("®", "").replace("™", "").strip()
    if p.get("isAccessory") or not re.search(r"(?i)roomba", name):
        pr.absences.append({"key": "*", "reason": "not a robot product", "source": "s1"})
        return pr
    pr.identifiers.append(RV.ident("mfr_model", code, "model", "irobot", series=p.get("_gtmMasterID")))
    pr.aliases.append({"text": "iRobot " + name, "kind": "marketing_name"})
    for pid, dv in sorted(var.items()):
        pv = dv.get("product") or {}
        colour = next((v.get("displayValue") for a in pv.get("variationAttributes") or [] if a.get("attributeId") == "color"
                       for v in a.get("values") or [] if v.get("selected")), None)
        if pid != code:
            pr.identifiers.append(RV.ident("mfr_sku", pid, "configuration", "irobot", role="alias", parent=code, option=colour))
        upc = re.sub(r"\D", "", pv.get("upc") or "")
        if len(upc) in (12, 13):
            pr.identifiers.append(RV.ident("gtin", upc, "configuration", "irobot", role="alias", parent=code, option=colour))
    rows = spec_rows(d.get("pdpSpecs") or "")

    def add(k, v, raw, label):
        RV.add(pr, ADAPTER, snap, code, k, v, raw, label)
    if not rows:
        pr.absences.append({"key": "*", "reason": "no Specifications rows in pdpSpecs", "source": "s1"})
    used = set()
    for lab, unit, v in rows:
        l = lab.lower()
        k0 = len(pr.claims)
        if l.startswith("retail box"):
            continue
        if l == "robot weight" and (w := weight(v, unit)):
            add("phys.robot_weight_g", RV.robot_weight(w), v, lab)
        elif l == "robot dimensions" and (dd := dims_in(v, unit, robot=True)):
            dd = RV.robot_dims(dd)
            add("phys.robot_dimensions", dd, v, lab); add("phys.robot_height_mm", RV.robot_height(dd), v, lab)
        elif re.search(r"\b(dock|clean base)\b.*dimensions", l) and (dd := dims_in(v, unit)):
            add("phys.dock_dimensions", dd, v, lab)
        elif re.search(r"\b(dock|clean base)\b.*weight", l) and (w := weight(v, unit)):
            add("phys.dock_weight_g", w, v, lab)
        elif l in ("dry bin capacity", "bin capacity", "dustbin capacity"):
            add("clean.dustbin_ml", RV.ml(v), v, lab)
        elif l in ("tank capacity", "water tank capacity"):
            add("mop.robot_tank_ml", RV.ml(v), v, lab)
        elif l.startswith("battery"):
            add("bat.capacity_mah", RV.mah(v.replace("mAH", "mAh")), v, lab)
        if len(pr.claims) > k0:
            used.add(lab)
    pr.fingerprints = {"raw": snap.snapshot, "labels": sorted({r[0] for r in rows}), "members": sorted(var), "unmapped": {r[0]: r[2][:80] for r in rows if r[0] not in used}}
    return pr


if __name__ == "__main__":
    _run.main(IrobotRobovac())
