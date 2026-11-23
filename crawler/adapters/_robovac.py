"""Shared robot-vacuum helpers (category robot-vacuums): Shopify catalogue discovery, SKU-overlap grouping, the bundle fetch, and pure value
parsers. Network only through crawl.Net (robots, <=1 req/s, breaker); parsers are pure.

Discovery (one source = one Shopify store): /products.json?limit=250&page=N (a few requests) -> keep robot-vacuum products (brand predicate) ->
group products that share ANY variant SKU (the manufacturer's material code) or derive the same model name: "App Only", "Live Only",
"Membership", "Complete" and colour pages of one robot are one model. Bundles without SKUs, refurbished units, accessories, stick and wet-dry
vacuums are dropped (recorded in the discovery checkpoint). One ref per model; hints carry the member handles.
Fetch: ONE snapshot per model = gzip JSON bundle {page_url, html (canonical product page), products: [/products/<handle>.json for every member]},
so the parse never depends on discovery.json (members' titles and SKUs are inside the snapshot). 1 + members requests.
"""
import gzip, html as H, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402

DELAY = 1.0
_NOT_UNIT = re.compile(r"(?i)refurb|trade[- ]in|warranty|subscription|service|gift|【")
_ACCESSORY = re.compile(r"(?i)\baccessor|replacement|dust bag|side brush|main brush|filter|mop (pad|cloth)|cleaning solution|wet[- ]?(and|&)?[- ]?dry|"
                        r"stick vacuum|cordless|handheld|pool|lawn|mower|window|purifier|bracket|stand\b")


class _Noise:
    """Not a robot-vacuum unit: refurbished / trade-in / warranty anywhere in the title; accessory words only in the title head (before
    ' with ' / ' - '), because robot titles name features ('... with Anti-Tangle Side Brush')."""
    def search(self, t):
        head = re.split(r"(?i)\s+with\s+|\s+[-–]\s+|,", t or "")[0]
        return _NOT_UNIT.search(t or "") or _ACCESSORY.search(head)


NOISE_TITLE = _Noise()


def catalogue(net, host, pages=30):
    """-> (products, stop_reason). Stops at the first empty page; any non-200 = incomplete."""
    out = []
    for page in range(1, pages + 1):
        r = net.get(f"https://{host}/products.json?limit=250&page={page}", DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return out, f"products.json page {page}: {getattr(r, 'status_code', r)}"
        ps = r.json().get("products") or []
        if not ps:
            return out, None
        out += ps
    return out, f"page cap {pages}"


def skus(p):
    return {v["sku"].strip() for v in p.get("variants", []) if v.get("sku") and v["sku"].strip()}


def group(products, model_of, prefer):
    """Union products sharing a SKU or a derived model name. -> [(model_name, canonical, members)] sorted by model name.
    model_of(p) -> name or None (None = not a robot vacuum); prefer(p) -> sort key (lower = better canonical page)."""
    ps = [p for p in products if model_of(p)]
    parent = list(range(len(ps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    by = {}
    for i, p in enumerate(ps):
        for k in [("sku", s) for s in skus(p)] + [("name", norm(model_of(p)))]:
            if k in by:
                parent[find(i)] = find(by[k])
            else:
                by[k] = i
    groups = {}
    for i, p in enumerate(ps):
        groups.setdefault(find(i), []).append(p)
    out = []
    for members in groups.values():
        members.sort(key=lambda p: (prefer(p), len(p["title"]), p["handle"]))
        out.append((model_of(members[0]), members[0], members))
    return sorted(out, key=lambda t: norm(t[0]))


def norm(s):
    return re.sub(r"[^A-Z0-9+]", "", (s or "").upper())


def refs_from_groups(source_id, host, groups):
    refs = []
    seen = set()
    for name, canon, members in groups:
        key = re.sub(r"[^a-z0-9]+", "-", plus(name).lower()).strip("-")
        if key in seen:
            key += "-" + canon["handle"][:20]
        seen.add(key)
        refs.append(C.Ref(source_id, key, f"https://{host}/products/{canon['handle']}",
                          {"model": name, "handles": [m["handle"] for m in members], "product_type": canon.get("product_type")}))
    return refs


def fetch_bundle(store, adapter, ref, net):
    """GET the canonical page + each member's product JSON; store one gzip JSON bundle. Any non-200 on the page = failed snapshot."""
    now = time.strftime("%FT%TZ", time.gmtime())
    r = net.get(ref.url, DELAY)
    if not hasattr(r, "status_code") or r.status_code != 200:
        s = C.Snapshot("sha256:", ref, getattr(r, "status_code", r) or "breaker", now, ref.url, {})
        store.append(s, adapter, ".json.gz")
        return s
    base = ref.url.split("/products/")[0]
    prods, missing = [], []
    for h in ref.hints.get("handles") or [ref.url.rsplit("/", 1)[1]]:
        j = net.get(f"{base}/products/{h}.json", DELAY)
        if hasattr(j, "status_code") and j.status_code == 200:
            try:
                prods.append(j.json()["product"])
                continue
            except (ValueError, KeyError):
                pass
        missing.append(h)
    body = {"page_url": r.url, "html": r.text, "products": prods, "missing": missing}
    blob = gzip.compress(json.dumps(body, sort_keys=True).encode(), 6, mtime=0)
    s = C.Snapshot(store.put(blob, ".json.gz"), ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
    store.append(s, adapter, ".json.gz")
    return s


def read_bundle(blobs, snap):
    return json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))


def text(s):
    s = re.sub(r"<sup[^>]*>.*?</sup>|<style.*?</style>|<script.*?</script>", "", s or "", flags=re.S)
    s = H.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", s).strip()


def page_lines(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    h = re.sub(r"</(li|p|div|tr|h\d)>|<br\s*/?>", "\n", h)
    return [l for l in (text(x) for x in h.split("\n")) if l]


# ---- value parsers (pure; return numbers in the profile unit, or None) ----------------------------------------------------------------
def _num(s):
    return float(s.replace(",", ""))


def pa(s):
    """'19,000Pa' / '30kPa' / '18500 Pa' -> Pa. A bare number is not suction."""
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k?)\s*Pa\b", s or "", re.I)
    if not m:
        return None
    v = _num(m[1]) * (1000 if m[2] else 1)
    return int(v) if 300 <= v <= 60000 else None


def mah(s):
    m = re.search(r"(\d[\d,]*)\s*mAh\b", s or "", re.I)
    return int(_num(m[1])) if m and 1000 <= _num(m[1]) <= 15000 else None


def wh(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*Wh\b", s or "")
    return _num(m[1]) if m else None


def ml(s):
    """'310ml' / '≥300ml' (qualifier dropped -> None) / '4.5L' / '3.2 L' -> mL."""
    if re.search(r"[≥>]|at least|min", s or "", re.I):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|mL|L|l)\b", s or "")
    if not m:
        return None
    return int(round(_num(m[1]) * (1 if m[2].lower() == "ml" else 1000)))


def tanks(s):
    """'4.5L/4.0L' (clean/used) -> (clean_ml, dirty_ml)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*L?\s*/\s*(\d+(?:\.\d+)?)\s*L\b", s or "")
    return (int(_num(m[1]) * 1000), int(_num(m[2]) * 1000)) if m else (None, None)


def length_mm(s):
    """'10.5mm (0.41in)' / '0.41in' / '2cm' -> mm (first figure; mm preferred when printed)."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", s or "")
    if m:
        return _num(m[1])
    m = re.search(r"(\d+(?:\.\d+)?)\s*cm\b", s or "")
    if m:
        return _num(m[1]) * 10
    m = re.search(r"(\d+(?:\.\d+)?)\s*(in\b|inch|\")", s or "")
    return round(_num(m[1]) * 25.4, 1) if m else None


def weight_g(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", s or "", re.I)
    if m:
        return round(_num(m[1]) * 1000)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:±\s*[\d.]+\s*)?lbs?\b", s or "", re.I)
    return round(_num(m[1]) * 453.592) if m and "±" not in s[: m.end()] else None


def dims_mm(s):
    """'13.78 x 13.78 x 3.82in' / '13.86*13.66*4.06 inches' / '350 × 350 × 97 mm' / '13.78in(350mm) x 13.78in(350mm) x 3.81in(97mm)'
    -> {length,width,height} mm (first triple only; printed mm preferred over converted inches)."""
    s = s or ""
    mms = re.findall(r"(\d+(?:\.\d+)?)\s*mm\b", s)
    if len(mms) >= 3 and re.search(r"[x×*]", s):
        a, b, c = (round(_num(x), 1) for x in mms[:3])
        return {"length": a, "width": b, "height": c}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:in|cm|mm)?\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(?:in|cm|mm)?\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(mm|cm|in|inch|inches|\")", s, re.I)
    if not m:
        return None
    f = {"mm": 1, "cm": 10}.get(m[4].lower(), 25.4)
    a, b, c = (round(_num(x) * f, 1) for x in m.groups()[:3])
    return {"length": a, "width": b, "height": c}


def power_mode(s):
    """Mode a runtime/noise figure was stated under (profile condition power_mode)."""
    t = (s or "").lower()
    for k, v in (("quiet", "quiet"), ("silent", "quiet"), ("lowest", "quiet"), ("standard", "standard"), ("balanced", "standard"),
                 ("turbo", "max"), ("max mode", "max"), ("maximum suction", "max")):
        if k in t:
            return v
    return "unstated"


def minutes(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(min|minutes|mins)\b", s or "", re.I)
    if m:
        return int(_num(m[1]))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(h|hr|hrs|hours)\b", s or "", re.I)
    return int(_num(m[1]) * 60) if m else None


def temp_c(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*C\b", s or "")
    if m:
        return _num(m[1])
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*[F℉]", s or "")
    return round((_num(m[1]) - 32) * 5 / 9) if m else None


def yes(s):
    """Tick-mark cells: '✓' / '√' / '✓ (167°F)' / 'Yes' -> True; '/' '-' 'No' '×' -> False; anything else None."""
    t = (s or "").strip()
    if re.match(r"^(✓|√|✔|yes|supported)", t, re.I):
        return True
    if re.match(r"^(/|-|—|no|×|✗|n/a)$", t, re.I):
        return False
    return None


def obstacle_sensors(s):
    t = (s or "").lower()
    out = []
    if re.search(r"structured light|3d light|line laser|laser", t):
        out.append("structured_light")
    if re.search(r"rgb|camera|ai vision|visual|vision", t):
        out.append("rgb_camera")
    if re.search(r"\btof\b|time of flight|dtof", t):
        out.append("tof")
    if re.search(r"infrared|\bir\b", t):
        out.append("infrared")
    if re.search(r"ultrasonic", t):
        out.append("ultrasonic")
    return out or None


def navigation(s):
    t = (s or "").lower()
    if re.search(r"dtof", t):
        return "dtof"
    if re.search(r"\blds\b|lidar|laser distance", t):
        return "lidar"
    if re.search(r"dtof", t):
        return "dtof"
    if re.search(r"vslam|camera|visual", t):
        return "vslam_camera"
    if re.search(r"gyro", t):
        return "gyroscope"
    return None


def mop_type(s):
    t = (s or "").lower()
    if re.search(r"roller", t):
        return "roller"
    if re.search(r"spinning|rotating|rotary|omni-scrub|dual.*mops?\b", t):
        return "dual_spinning"
    if re.search(r"vibrat|sonic", t):
        return "vibrating_pad"
    if re.search(r"track|crawler", t):
        return "track"
    if re.search(r"pad|cloth", t):
        return "static_pad"
    return None


def basis_for(number_literal, disclaimers):
    """Which disclaimer qualifies a headline number. -> (basis, quote) with basis in the profile's claim_basis enum."""
    pat = re.escape(number_literal.replace(",", "")).replace("\\ ", r"\s*")
    for d in disclaimers:
        if re.search(pat, d.replace(",", ""), re.I):
            if re.search(r"t[uü]v|sgs|intertek|\bul\b|certified by", d, re.I):
                return "third_party_certified", d
            if re.search(r"in-house|our lab|internal lab|laboratory", d, re.I):
                return "mfr_in_house_lab", d
    return "mfr_unstated", None


def add(pr, adapter, snap, model, key, value, raw, label, conditions=None, quote=None):
    """One manufacturer claim on the model (locator model_code); skips empty values. raw = the source literal, never rewritten."""
    if value in (None, "", [], {}):
        return
    raw = raw if isinstance(raw, str) else " | ".join(raw)
    model = plus(model)
    pr.claims.append(C.claim(model, key, value, None, raw, "s1", adapter, "adapter", snap.fetched_at,
                             locator={"model_code": model, "label": label}, quote=quote, conditions=conditions))


def plus(name):
    """'Q7 Max+' -> 'Q7 Max Plus'. Brands spell the self-empty suffix both ways (Roborock 'Q5 Max+', Dreame 'D20 Pro Plus'); the canonical model
    value uses 'Plus' so 'Q7 Max' and 'Q7 Max+' never collapse into one id slug. value_raw keeps the literal."""
    return re.sub(r"\s*\+(?=\s|$)", " Plus", name).strip()


def ident(scheme, value, level, issuer, role="key", market="US", raw=None, **extra):
    d = {"scheme": scheme, "value": value, "value_raw": raw or value, "issuer": issuer, "market": market, "package_level": level, "role": role, "sources": ["s1"]}
    d.update(extra)
    return d


def variant_idents(pr, products, issuer, model, sku_norm=lambda s: s):
    """Every member product's variant SKU (+ barcode) becomes a configuration-level alias of the model: colours / app-only / live-only /
    'Complete' pages of one robot group into the model, SKUs are kept as aliases with their option label (colour)."""
    seen = set()
    for p in products:
        for v in p.get("variants", []):
            s = (v.get("sku") or "").strip()
            if s and sku_norm(s) not in seen:
                seen.add(sku_norm(s))
                opt = " / ".join(x for x in (v.get("option1"), v.get("option2")) if x and x != "Default Title")
                pr.identifiers.append(ident("mfr_sku", sku_norm(s), "configuration", issuer, role="alias", parent=model, option=opt or None))
            b = re.sub(r"\D", "", v.get("barcode") or "")
            if len(b) in (12, 13) and b not in seen:
                seen.add(b)
                pr.identifiers.append(ident("gtin", b, "configuration", issuer, role="alias", parent=model))
        if p.get("title"):
            pr.aliases.append({"text": text(p["title"]), "kind": "retail_title"})


def plausible_robot(dims=None, weight_g=None):
    """Guard against cells that mix robot + dock (Roborock 'Robot&Dock Size', 'Robot Weight 32.19 lbs'): a robot body is 200-450 mm across,
    50-150 mm tall and 1.5-7.5 kg. Out of range -> the claim is not emitted (recorded in fingerprints.implausible), never 'corrected'."""
    if dims is not None:
        return all(200 <= dims[k] <= 450 for k in ("length", "width")) and 50 <= dims["height"] <= 150
    if weight_g is not None:
        return 1500 <= weight_g <= 7500
    return False
