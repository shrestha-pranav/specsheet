#!/usr/bin/env python3
"""Levoit US air purifiers adapter v1 (contract ARCHITECTURE 15.5), category air-purifiers.

discover : levoit.com Shopify /products.json (robots allows it), product_type 'Air Purifier'; bundles (title 'Bundle', '&', '+') and
           filters are skipped. 1 req / 1.5 s.
fetch    : the product page, gzip-stored.
parse    : pure. Only the labelled 'Product Specifications' list (<strong>Label</strong>: value) and the 'Features' bullet list.
Identity : mfr_model = the page's own 'Model' row (Levoit prints the marketing model, 'Core 400S', not the LAP-C401S-WUSR label code; the
           two are NOT joined: identity.md). A page without a Model row yields an absence and no entity. Title -> marketing_name alias.
Rules    : 'CADR: 231 CFM' names no pollutant -> cadr.unspecified_cfm (preview: smoke is NOT assumed). 'Ideal Room Size: 1718 ft2 (1 ACH) /
           358 ft2 (4.8 ACH)' -> room.coverage_sqft{ach:1} and room.size_sqft{room_basis: maker_stated_ach, ach:4.8}; a figure with no ACH is
           room.coverage_sqft without ach. 'Noise Level: 22–52dB' -> noise.db{fan_speed: range_min|range_max}. 'Rated Power' ->
           pwr.rated_w{power_basis: maker_rated}; 'Standby Power: < 2W' is a bound -> unresolved. Dimensions print no axis order ->
           phys.dimensions_text only. Features: only exact items ('Wi-Fi Indicator' / 'Sleep Mode' / 'Check Filter Indicator') -> True.
"""
import gzip, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _airpurifier as A
import _run

ID, VERSION, SOURCE = "levoit_airpurifiers", 1, "levoit-us-airpurifiers"
CATEGORIES = {"air-purifiers"}
BASE = "https://levoit.com"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.5
SPEC = re.compile(r"<li>\s*<strong>([^<]{2,60})</strong>\s*:\s*(.*?)</li>", re.S)
FEAT = {"wi-fi indicator": "smart.wifi", "wifi indicator": "smart.wifi", "sleep mode": "feat.sleep_mode", "check filter indicator": "feat.filter_indicator",
        "filter indicator": "feat.filter_indicator", "timer": "feat.timer", "auto mode": "feat.auto_mode"}


class LevoitAirPurifiers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        items, page = [], 1
        while page < 10:
            r = net.get(f"{BASE}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return Discovery([], False, f"products.json page {page}: {getattr(r, 'status_code', r)}", checkpoint or {})
            p = r.json().get("products", [])
            if not p:
                break
            items += p; page += 1
        refs = []
        for p in items:
            if p.get("product_type", "").strip().lower() != "air purifier" or re.search(r"bundle|&|\+|filter", p["title"], re.I):
                continue
            refs.append(Ref(SOURCE, p["handle"], f"{BASE}/products/{p['handle']}", {"title": p["title"], "skus": [v.get("sku") for v in p["variants"]]}))
        return Discovery(refs, True, None, {"products": len(items), "purifiers": len(refs)})

    def fetch(self, ref, prior, net):
        r = net.get(ref.url, DELAY)
        now = time.strftime("%FT%TZ", time.gmtime())
        if r is None or isinstance(r, str) or r.status_code != 200:
            s = C.Snapshot("sha256:", ref, (r if (r is None or isinstance(r, str)) else r.status_code) or "breaker", now, ref.url, {})
            self.store.append(s, ADAPTER, ".html.gz")
            return s
        sha = self.store.put(gzip.compress(r.content, 6, mtime=0), ".html.gz")
        s = C.Snapshot(sha, ref, 200, now, r.url, {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, ADAPTER, ".html.gz")
        return s

    def parse(self, snap, blobs, profile):
        return parse_html(snap, gzip.decompress(blobs.read(snap.snapshot, ".html.gz")).decode("utf-8", "replace"))


def blocks(h):
    """-> {heading: inner html} of the product accordion <details> blocks."""
    out = {}
    for m in re.finditer(r'<h2 class="text-lg font-light">([^<]+)</h2>(.*?)</details>', h, re.S):
        out.setdefault(A.clean(m.group(1)), m.group(2))
    return out


def parse_html(snap, h):
    pr, obs = ParseResult(), snap.fetched_at
    b = blocks(h)
    rows = {}
    for lab, v in SPEC.findall(b.get("Product Specifications") or b.get("Product Specification") or ""):
        rows.setdefault(A.clean(lab), A.clean(v))
    model = rows.get("Model")
    if not model or not A.model_ok(model):
        pr.absences.append({"key": "*", "reason": "no 'Model' row in the Product Specifications list", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "rows": len(rows)}
        return pr
    pr.sources = [{"id": "s1", "url": snap.final_url or snap.ref.url, "label": "Levoit US product page " + model, "source_id": SOURCE,
                   "tier": "manufacturer", "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "levoit", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    for sku in (snap.ref.hints or {}).get("skus") or []:
        if sku:
            pr.identifiers.append({"scheme": "x_levoit_sku", "value": sku, "value_raw": sku, "issuer": "levoit", "role": "alias", "sources": ["s1"]})
    t = A.clean((snap.ref.hints or {}).get("title") or "")
    if t:
        pr.aliases.append({"text": t[:100], "kind": "marketing_name", "source": "s1", "observed_at": obs})
    used = set()

    def add(key, value, unit, label, cond=None, status="known"):
        raw = f"{label}: {rows.get(label, '')}"[:300]
        pr.claims.append(claim(model, key, value, unit, raw, "s1", ADAPTER, "html_table", obs, {"label": label}, raw, conditions=cond, status=status))
        used.add(label)

    v = rows.get("Rated Power")
    if v:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*W(?:,\s*\d+(?:\.\d+)?\s*A)?", v)
        add("pwr.rated_w", A.intish(float(m.group(1))) if m else None, "W", "Rated Power", {"power_basis": "maker_rated"}, "known" if m else "unknown")
    v = rows.get("Standby Power")
    if v:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*W", v)
        add("pwr.standby_w", A.intish(float(m.group(1))) if m else None, "W", "Standby Power", {"power_basis": "maker_unstated"}, "known" if m else "unknown")
    for lab in ("Voltage", "Power Supply"):
        if rows.get(lab):
            add("pwr.voltage", rows[lab], None, lab)
            break
    v = rows.get("CADR")
    if v:
        m = re.fullmatch(r"(\d{2,4})\s*CFM(?:\s*/\s*[\d.]+\s*m³/h)?", v, re.I)
        add("cadr.unspecified_cfm", int(m.group(1)) if m else None, "cfm", "CADR", {"cadr_basis": "maker_claimed"}, "known" if m else "unknown")
    v = rows.get("CADR*")
    if v:      # labelled per pollutant; basis AHAM only when the same list affirmatively says so ('Certified: Aham Verifide')
        aham = bool(re.fullmatch(r"aham verifide(d)?( certified)?", rows.get("Certified", ""), re.I))
        for pol in ("Smoke", "Dust", "Pollen"):
            m = re.search(pol + r":\s*(\d{2,4})\s*CFM", v)
            if m:
                add(f"cadr.{pol.lower()}_cfm", int(m.group(1)), "cfm", "CADR*", {"cadr_basis": "aham_verified_maker_stated" if aham else "maker_claimed"})
        if aham:
            used.add("Certified")
    v = rows.get("Ideal Room Size")
    if v:
        for part in re.split(r"\s*/\s*(?=\d)", v):
            m = re.match(r"([\d,]+)\s*(?:ft2|ft²|sq\.?\s*ft)\.?\s*(?:\((\d+(?:\.\d+)?)\s*ACH\))?", part, re.I)
            if not m:
                continue
            area, ach = int(m.group(1).replace(",", "")), (float(m.group(2)) if m.group(2) else None)
            if ach is not None and abs(ach - 4.8) < 0.05:
                add("room.size_sqft", area, "ft2", "Ideal Room Size", {"room_basis": "maker_stated_ach", "ach": 4.8})
            else:
                add("room.coverage_sqft", area, "ft2", "Ideal Room Size", {"ach": A.intish(ach)} if ach is not None else None)
    v = rows.get("Noise Level")
    if v:
        nc = A.noise_claims(v)
        for val, sp in nc:
            add("noise.db", val, "dB", "Noise Level", {"fan_speed": sp})
        if not nc:
            add("noise.db", None, "dB", "Noise Level", None, "unknown")
    v = rows.get("Weight")
    if v:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*lbs?\.?(?:\s*/\s*[\d.]+\s*kg)?", v, re.I)
        add("phys.weight_lb", float(m.group(1)) if m else None, "lb", "Weight", None, "known" if m else "unknown")
    if rows.get("Dimensions"):
        add("phys.dimensions_text", rows["Dimensions"], None, "Dimensions")
    feats = [A.clean(x) for x in re.findall(r"<li>(.*?)</li>", b.get("Features", ""), re.S)]
    for f in feats:
        k = FEAT.get(f.lower().strip())
        if k and not any(c["key"] == k for c in pr.claims):
            q = f"Features: {f}"
            pr.claims.append(claim(model, k, True, None, q, "s1", ADAPTER, "html_table", obs, {"label": "Features"}, q))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "rows": len(rows), "unmapped": {k: v for k, v in rows.items() if k not in used | {"Model"}},
                       "features": feats}
    return pr


if __name__ == "__main__":
    _run.main(LevoitAirPurifiers())
