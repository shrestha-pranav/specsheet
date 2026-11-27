"""USB-IF certified-product overlay (A2-usbif r12, transform usbif-attach@1, extractor usbif_products@1). Called by import.py after every
source and transform has built its entities; reads only the stored snapshot raw/usbif-certified-products (crawler/adapters/usbif_products.py,
one GET of www.usb.org/vtm-products/v1/all; nothing from the network here).

What it does: attaches cert.usb_if facts to EXISTING chargers / power-banks / laptops entities. It never mints an entity, never merges, never
creates a cables category (brief coord-2026-11-26-r12).

Identity rule (fail closed):
  - the listing company must be on COMPANIES (an explicit company -> our brand map). An OEM / ODM listing (Channel Well, Luxshare, Best Buy
    China, ...) never binds, even when its part number equals one of our model numbers: identity_events usbif_proposal reason oem_listing;
  - a row's identity tokens are its field_usb_model_part_number cell split on , ; / (a 'PN:' prefix dropped); the product name cell is read
    ONLY when the part-number cell is empty, and then only when it is a model list (every token has a digit, no spaces inside a token);
  - a token binds when it EQUALS (identity.norm_value, same brand) one of the entity's own mfr_model / mfr_sku / mtm identifiers. No prefix,
    stem, family or suffix matching;
  - the row's product type must be the category's (chargers: Power Brick; power-banks: Power Bank; laptops: Systems > Notebooks), otherwise
    usbif_proposal reason type_mismatch (a maker's cable with the same code as its charger is not the charger);
  - status Obsolete rows and rows without a TID attach nothing. Absent from the list = unknown, never false.
Facts (extractor usbif_products@1, tier certifier, source = the stored JSON snapshot with a '#tid=' fragment per listing):
  cert.usb_if = true; with exactly one bound TID also cert.usb_if_tid, cert.usb_if_date (global_pass_date, date part) and
  cert.usb_if_product_type. Several TIDs on one entity: cert.usb_if per TID only (the TID / date stay on each source's locator).
"""
import collections, hashlib, html, re, sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "crawler" / "adapters"))
sys.path.insert(0, str(CODE / "scripts"))
import identity as I  # noqa: E402

ID, VERSION = "usbif-attach", 1
TRANSFORM = f"{ID}@{VERSION}"
EXTRACTOR = "usbif_products@1"
SOURCE_ID = "usbif-certified-products"
URL = "https://www.usb.org/vtm-products/v1/all"
KEYS = ("cert.usb_if", "cert.usb_if_tid", "cert.usb_if_date", "cert.usb_if_product_type")
SCHEMES = ("mfr_model", "mfr_sku", "mtm")
# Listing company (device_company_view_field, exact) -> our brand id. Only companies that ARE the brand; OEMs never appear here.
COMPANIES = {"ASUSTek Computer Inc.": "asus", "Dell Inc.": "dell", "Lenovo": "lenovo", "Microsoft Corporation": "microsoft",
             "Nekteck, Inc.": "nekteck", "Razer Inc": "razer", "Samsung Electronics Co., Ltd.": "samsung", "Ugreen Group Limited": "ugreen",
             "Acer, Inc.": "acer", "HP Inc.": "hp", "Hypercel Corporation": "hypercel"}
CATEGORY_TYPES = {"chargers": "power_brick", "power-banks": "power_bank", "laptops": "notebook"}
PD_TYPES = {"power brick": "power_brick", "power bank": "power_bank", "pd controller": "pd_controller",
            "single port power sinking device (psd)": "psd"}


def fingerprint():
    h = hashlib.sha256()
    for p in (Path(__file__), CODE / "crawler/adapters/usbif_products.py"):
        h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()[:20]


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(str(s or ""))).strip()


def product_type(r):
    pd = PD_TYPES.get(clean(r.get("field_pd_silicon_and_brick_marke_1")).lower())
    if pd:
        return pd
    cat = clean(r.get("field_device_category"))
    if re.search(r"\bNotebooks\b", cat):
        return "notebook"
    if clean(r.get("field_cable_marketing_category")) or re.search(r"Cable Assembl", cat) or clean(r.get("field_usb_cable_max_speed")):
        return "cable"
    return "other"


def tokens(r):
    """-> [(token, field)]: the row's identity tokens (module docstring)."""
    pn = clean(r.get("field_usb_model_part_number"))
    if pn:
        parts, field = re.split(r"[,;/]", pn), "field_usb_model_part_number"
    else:
        parts, field = re.split(r"[,;]", clean(r.get("name"))), "name"
    out = []
    for t in parts:
        t = re.sub(r"^\s*PN\s*:\s*", "", t, flags=re.I).strip()
        if not t:
            continue
        if field == "name" and " " in t:
            return []                     # a product description, not a model list: the name cell names nothing
        if " " in t or len(t) < 4 or len(t) > 40 or not re.search(r"\d", t) or not re.search(r"[A-Za-z0-9]", t):
            continue
        out.append((t, field))
    return out


def load(root=None):
    import usbif_products as U
    import _contract as C
    store = C.BlobStore(SOURCE_ID) if root is None else _Store(Path(root) / "raw" / SOURCE_ID)
    rec, data = U.latest(store)
    rows = list(data.values()) if isinstance(data, dict) else list(data or [])
    return rec, rows


class _Store:
    def __init__(self, d):
        self.dir = d

    def snapshots(self):
        import json
        p = self.dir / "snapshots.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    def read(self, snapshot, ext):
        return (self.dir / "blobs" / f"{snapshot.split(':', 1)[1]}{ext}").read_bytes()


def _claim(key, value, raw, loc, obs, quote):
    import _contract as C
    c = C.claim(loc["matched"], key, value, None, raw, "s1", EXTRACTOR, "feed", obs, dict(loc), quote)
    return c


def apply(worlds, events, stats, root=None, rows=None, rec=None):
    """worlds: {category: World} of import.py. -> Counter (also merged into stats). rows/rec: tests pass a fixture instead of raw/."""
    st = collections.Counter()
    if rows is None:
        rec, rows = load(root)
    if not rec or not rows:
        st["usbif_no_snapshot"] += 1
        stats.update(st)
        return st
    st["usbif_rows"] = len(rows)
    # (brand, scheme, normalised value) -> [(world, entity)] over the categories this overlay serves
    idx, brands = collections.defaultdict(list), set()
    for cat in CATEGORY_TYPES:
        w = worlds.get(cat)
        if w is None:
            continue
        for e in w.ents:
            for (sch, v), d in e.idents.items():
                if sch in SCHEMES and d.get("valid", True):
                    idx[(e.brand, sch, v)].append((w, e))
                    brands.add(e.brand)

    def lookup(t, brand):
        out = []
        for sch in SCHEMES:
            for h in idx.get((brand, sch, I.norm_value(sch, t, brand)), []):
                if h not in out:
                    out.append(h)
        return out

    bound = collections.defaultdict(list)          # entity -> [(row, token, field, world, ptype)]
    for r in rows:
        tid = clean(r.get("device_tid"))
        status = clean(r.get("field_device_status"))
        company = clean(r.get("device_company_view_field"))
        brand = COMPANIES.get(company)
        ptype = product_type(r)
        st[f"usbif_rows_type:{ptype}"] += 1
        for t, field in tokens(r):
            if brand is None:            # OEM / ODM listing: never binds, proposal when the code equals one of our models (any brand)
                for b in sorted(brands):
                    for w, e in lookup(t, b):
                        st["usbif_oem_listing_proposals"] += 1
                        events.append(("usbif_proposal", w.category, e, w.anchors(e.keys), (SOURCE_ID, f"tid:{tid}", rec["snapshot"]),
                                       {"reason": "oem_listing", "tid": tid, "company": company, "token": t,
                                        "name": clean(r.get("name"))[:80], "product_type": ptype}))
                continue
            for w, e in lookup(t, brand):
                if status != "Pass" or not tid:
                    st["usbif_skipped_not_pass_or_no_tid"] += 1
                    continue
                if CATEGORY_TYPES[w.category] != ptype:
                    st["usbif_type_mismatch_proposals"] += 1
                    events.append(("usbif_proposal", w.category, e, w.anchors(e.keys), (SOURCE_ID, f"tid:{tid}", rec["snapshot"]),
                                   {"reason": "type_mismatch", "tid": tid, "token": t, "product_type": ptype}))
                    continue
                if not any(x[0] is r for x in bound[e]):
                    bound[e].append((r, t, field, w, ptype))
    for e, hits in bound.items():
        w = hits[0][3]
        tids = sorted({clean(r.get("device_tid")) for r, *_ in hits})
        for r, t, field, w, ptype in hits:
            tid = clean(r.get("device_tid"))
            date = clean(r.get("global_pass_date"))[:10] or None
            snap = f"{rec['snapshot']}#tid={tid}"
            e.srcs.setdefault(snap, {"url": f"{URL}#tid={tid}", "tier": "certifier", "label": f"USB-IF Certified Product List, TID {tid}",
                                     "snapshot": snap, "retrieved_at": rec.get("fetched_at")})
            ob = (SOURCE_ID, f"tid:{tid}", snap)
            obs_at = rec.get("fetched_at") or "1970-01-01T00:00:00Z"
            loc = {"usbif_tid": tid, "usbif_row_id": clean(r.get("id")), "matched": t, "field": field, "certified": date,
                   "company": clean(r.get("device_company_view_field"))}
            quote = f"USB-IF certified product TID {tid}, {clean(r.get('name'))[:120]} ({loc['company']}), passed {date or '(undated)'}"
            raw = f"{field}: {clean(r.get(field))[:120]} | TID {tid} | {clean(r.get('field_device_status'))} | {date}"
            cs = [_claim("cert.usb_if", True, raw, loc, obs_at, quote)]
            if len(tids) == 1:
                cs.append(_claim("cert.usb_if_tid", tid, raw, loc, obs_at, quote))
                if date:
                    cs.append(_claim("cert.usb_if_date", date, raw, loc, obs_at, quote))
                cs.append(_claim("cert.usb_if_product_type", ptype, raw, loc, obs_at, quote))
            for c in cs:
                e.claims.append((c, ob))
                st[f"usbif_claims:{w.category}:{c['key']}"] += 1
            e.obs.add(ob)
        st[f"usbif_entities:{w.category}"] += 1
        events.append(("usbif_attach", w.category, e, w.anchors(e.keys), (SOURCE_ID, f"tid:{tids[0]}", rec["snapshot"]), {"tids": tids}))
    stats.update(st)
    return st


def digest_rows(root=None):
    """(source_id, ref, snapshot) rows for import.py's raw-snapshot digest (release inputs)."""
    rec, _ = load(root)
    return [(SOURCE_ID, "_all", rec["snapshot"])] if rec else []
