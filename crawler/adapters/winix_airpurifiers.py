#!/usr/bin/env python3
"""Winix America air purifiers adapter v1 (contract ARCHITECTURE 15.5), category air-purifiers.

discover : https://www.winixamerica.com/product-sitemap.xml (robots `User-agent: *` Allow /; Yoast sitemap) -> /product/<slug>/ pages.
           Filters ('filter-'), aroma pads and refurbished listings are skipped (a refurbished unit is a sales condition, not a model).
fetch    : the WooCommerce product page, gzip-stored. 1 req / 1.5 s.
parse    : pure. Only the labelled WooCommerce 'Additional information' table (th label / td value) and the 'Replacement Filter' tab.
Identity : mfr_model = the 'Model Name' row (C545, 5500-2, XQ Pro). No row -> absence, no entity.
Rules    : CADR row 'CADR (Dust / Pollen / Smoke)': the pollutant order is read from the LABEL, never assumed. cadr_basis =
           aham_verified_maker_stated only when the same table affirmatively names AHAM (an 'AHAM Verified Room Size' row or AHAM in the
           Certifications row), else maker_claimed. 'AHAM Verified Room Size' -> room.size_sqft{room_basis: aham_verified_maker_stated};
           'Maximum Room Coverage' -> room.coverage_sqft (ACH unstated). 'HEPA Filter (Filter Life): 99.97% True HEPA (12M)' ->
           filter.true_hepa=True only on the words 'True HEPA' (never false) and filter.life_months{filter_stage: hepa}. 'Minimum Noise
           Level' -> noise.db{fan_speed: lowest}. Bool rows (Timer, Auto Mode, Filter Replacement Indicator) are True on Yes/a schedule and
           False only on a bare 'No'. 'Smart Feature(s): WiFi / Alexa' -> smart.wifi True + smart.voice [alexa]; bare 'No'/'None' -> wifi
           False. Dimensions only when the label names the axis order (W x D x H). Replacement Filter tab: part number from the single
           filter product's title ('Filter S - 1712-0096-00'); its displayed price -> filter.price_usd (preview, dated by observation).
"""
import gzip, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _airpurifier as A
import _run

ID, VERSION, SOURCE = "winix_airpurifiers", 1, "winix-us-airpurifiers"
CATEGORIES = {"air-purifiers"}
SITEMAP = "https://www.winixamerica.com/product-sitemap.xml"
ADAPTER = f"{ID}@{VERSION}"
DELAY = 1.5
ROW = re.compile(r'<th class="woocommerce-product-attributes-item__label"[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>', re.S)
SKIP = re.compile(r"/product/(filter-|.*aroma|.*refurbished|certified-refurbished)", re.I)
YES = re.compile(r"^(yes|automatic\b.*|\d+(\s*,\s*\d+)*\s*(h|hr|hrs|hours?)\b.*)$", re.I)


class WinixAirPurifiers:
    id, version, source_id, categories = ID, VERSION, SOURCE, CATEGORIES

    def __init__(self):
        self.store = C.BlobStore(SOURCE)

    def discover(self, checkpoint, net):
        r = net.get(SITEMAP, DELAY)
        if not hasattr(r, "status_code") or r.status_code != 200:
            return Discovery([], False, f"sitemap {getattr(r, 'status_code', r)}", checkpoint or {})
        urls = sorted(set(re.findall(r"<loc>(https://www\.winixamerica\.com/product/[^<]+)</loc>", r.text)))
        refs = [Ref(SOURCE, u.rstrip("/").rsplit("/", 1)[1], u, {}) for u in urls if not SKIP.search(u)]
        return Discovery(refs, True, None, {"sitemap_products": len(urls), "refs": len(refs)})

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


def table(h):
    out = {}
    for lab, v in ROW.findall(h):
        out.setdefault(A.clean(lab), A.clean(v))
    return out


def replacement_filter(h):
    """-> (part_number, filter_letter, price, title) from the Replacement Filter tab when it shows exactly one filter product."""
    i = h.find('id="tab-replacement_filter"')
    if i < 0:
        return None
    seg = h[i:i + 20000]
    j = seg.find('role="tabpanel"', 40)
    seg = seg[:j] if j > 0 else seg
    titles = set(re.findall(r'alt="(Filter [A-Z0-9]{1,3}\s*-\s*[0-9][0-9-]{4,16})"', seg))
    if len(titles) != 1:
        return None
    t = titles.pop()
    m = re.match(r"Filter ([A-Z0-9]{1,3})\s*-\s*([0-9][0-9-]{4,16})", t)
    orig = re.findall(r"Original price was: &#0?36;([0-9]+\.[0-9]{2})", seg)
    cur = re.findall(r"Current price is: &#0?36;([0-9]+\.[0-9]{2})", seg)
    if orig or cur:      # the store's own screen-reader labels: 'Original price was' = list, 'Current price is' = sale (when an original exists)
        prices = [(x, "list") for x in orig] + [(x, "sale" if orig else "displayed") for x in cur]
    else:
        prices = [(x, "displayed") for x in re.findall(r'woocommerce-Price-currencySymbol">&#36;</span>([0-9]+\.[0-9]{2})', seg)]
    return m.group(2), m.group(1), prices, t


def parse_html(snap, h):
    pr, obs = ParseResult(), snap.fetched_at
    rows = table(h)
    model = rows.get("Model Name")
    if not model or not (A.model_ok(model) or re.fullmatch(r"[A-Z]{2,}[A-Z0-9-]*", model)):
        pr.absences.append({"key": "*", "reason": "no 'Model Name' row in the Additional information table", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "rows": len(rows)}
        return pr
    if not any(k.startswith(("CADR", "AHAM Verified Room Size", "HEPA Filter")) for k in rows):
        pr.absences.append({"key": "*", "reason": "no CADR / AHAM room size / HEPA row: not an air cleaner page (humidifier etc.)", "source": "s1"})
        pr.fingerprints = {"raw": snap.snapshot, "rows": len(rows)}
        return pr
    pr.sources = [{"id": "s1", "url": snap.final_url or snap.ref.url, "label": "Winix America product page " + model, "source_id": SOURCE,
                   "tier": "manufacturer", "retrieved_at": obs, "snapshot": snap.snapshot}]
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": "winix", "market": "US", "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    if t:
        pr.aliases.append({"text": A.clean(t.group(1))[:100], "kind": "marketing_name", "source": "s1", "observed_at": obs})
    used = {"Model Name"}

    def add(key, value, unit, label, cond=None, status="known"):
        raw = f"{label}: {rows.get(label, '')}"[:300]
        pr.claims.append(claim(model, key, value, unit, raw, "s1", ADAPTER, "html_table", obs, {"label": label}, raw, conditions=cond,
                               status=status if value is not None or status != "known" else "unknown"))
        used.add(label)

    certs = rows.get("Certifications", "")
    aham = "AHAM Verified Room Size" in rows or bool(re.search(r"\bAHAM\b", certs))
    basis = "aham_verified_maker_stated" if aham else "maker_claimed"
    for lab, v in rows.items():
        m = re.fullmatch(r"CADR\s*\(([A-Za-z /]+)\)", lab)
        if not m:
            continue
        names = [x.strip().lower() for x in m.group(1).split("/")]
        vals = [x.strip() for x in v.split("/")]
        if len(names) == len(vals) and set(names) <= {"dust", "pollen", "smoke"} and len(set(names)) == len(names):
            for n, x in zip(names, vals):      # '>450' (AHAM pollen cap) is a bound: that one value unresolved, the others kept
                ok = re.fullmatch(r"\d{2,4}", x)
                add(f"cadr.{n}_cfm", int(x) if ok else None, "cfm", lab, {"cadr_basis": basis}, "known" if ok else "unknown")
        else:
            add("cadr.unspecified_cfm", None, "cfm", lab, {"cadr_basis": basis}, "unknown")
    v = rows.get("AHAM Verified Room Size")
    if v:
        n = re.fullmatch(r"([\d,]+)\s*sq\.?\s*ft\.?", v, re.I)
        add("room.size_sqft", int(n.group(1).replace(",", "")) if n else None, "ft2", "AHAM Verified Room Size", {"room_basis": "aham_verified_maker_stated"})
    v = rows.get("Maximum Room Coverage")
    if v:
        n = re.fullmatch(r"([\d,]+)\s*sq\.?\s*ft\.?", v, re.I)
        add("room.coverage_sqft", int(n.group(1).replace(",", "")) if n else None, "ft2", "Maximum Room Coverage")
    for lab in rows:
        if lab.startswith("Clean Air Changes per Hour"):
            n = re.fullmatch(r"\d+(\.\d+)?", rows[lab])
            add("room.ach_at_size", float(rows[lab]) if n else None, None, lab)
    v = rows.get("Minimum Noise Level")
    if v:
        n = re.fullmatch(r"(\d{2}(?:\.\d)?)\s*dB", v)
        add("noise.db", A.intish(float(n.group(1))) if n else None, "dB", "Minimum Noise Level", {"fan_speed": "lowest"})
    for lab, stage in (("HEPA Filter (Filter Life)", "hepa"), ("Deodorization Filter (Filter Life)", "carbon")):
        v = rows.get(lab)
        if not v:
            continue
        n = re.search(r"\((\d{1,2})\s*M\)\s*$", v)
        add("filter.life_months", int(n.group(1)) if n else None, "month", lab, {"filter_stage": stage})
        if stage == "hepa" and re.search(r"\btrue hepa\b", v, re.I) and not re.search(r"\b(not|non|type|like|style)\b", v, re.I):
            add("filter.true_hepa", True, None, lab)
        if stage == "carbon" and re.search(r"activated carbon", v, re.I):
            add("filter.types", "activated_carbon", None, lab, {"filter_stage": "carbon"})
    v = rows.get("Number of Fan Speeds")
    if v:
        add("fan.speeds", int(v) if v.isdigit() else None, None, "Number of Fan Speeds")
    for lab, key in (("Timer", "feat.timer"), ("Auto Mode", "feat.auto_mode"), ("Filter Replacement Indicator", "feat.filter_indicator"),
                     ("Sleep Mode", "feat.sleep_mode")):
        v = rows.get(lab)
        if v:
            add(key, True if YES.match(v) else False if v.strip().lower() == "no" else None, None, lab)
    v = rows.get("Smart Feature(s)")
    if v:
        parts = {x.strip().lower() for x in re.split(r"[/,]", v)}
        if parts & {"wifi", "wi-fi"}:
            add("smart.wifi", True, None, "Smart Feature(s)")
        elif v.strip().lower() in ("no", "none"):
            add("smart.wifi", False, None, "Smart Feature(s)")
        voice = sorted({"alexa" if "alexa" in p else "google_assistant" for p in parts if "alexa" in p or "google" in p})
        if voice:
            add("smart.voice", voice, None, "Smart Feature(s)")
    v = rows.get("Advanced Technologies")
    if v and re.fullmatch(r"PlasmaWave®?( Technology)?", v, re.I):
        add("tech.technologies", ["plasmawave"], None, "Advanced Technologies")
    v = rows.get("Product Weight (lbs)")
    if v:
        add("phys.weight_lb", float(v) if re.fullmatch(r"\d+(\.\d+)?", v) else None, "lb", "Product Weight (lbs)")
    for lab, v in rows.items():
        m = re.fullmatch(r"Product Dimensions \(([WDH])[”\"]?\s*x\s*([WDH])[”\"]?\s*x\s*([WDH])[”\"]?\)", lab)
        n = re.fullmatch(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", v)
        if m and n and len(set(m.groups())) == 3:
            for ax, x in zip(m.groups(), n.groups()):
                add({"W": "phys.width_in", "D": "phys.depth_in", "H": "phys.height_in"}[ax], float(x), "in", lab)
        elif lab.startswith("Product Dimensions"):
            add("phys.dimensions_text", v, None, lab)
    v = rows.get("Warranty")
    if v:
        n = re.fullmatch(r"(\d{1,2})[- ]Years?", v, re.I)
        add("sup.warranty_years", int(n.group(1)) if n else None, None, "Warranty")
    if certs:
        add("cert.maker_listed", [x.strip() for x in certs.split("/") if x.strip()], None, "Certifications")
    rf = replacement_filter(h)
    if rf:
        pn, letter, prices, title = rf
        q = f"Replacement Filter tab: {title}"
        pr.claims.append(claim(model, "filter.part_number", pn, None, q, "s1", ADAPTER, "html_table", obs, {"label": "Replacement Filter"}, q,
                               conditions={"filter_stage": "set"}))
        bases = {}
        for x, bs in prices:
            bases.setdefault(bs, set()).add(x)
        for bs, xs in sorted(bases.items()):
            lit = q + " " + " / ".join("$" + x for x in sorted(xs)) + f" ({bs})"
            ok = len(xs) == 1
            pr.claims.append(claim(model, "filter.price_usd", float(next(iter(xs))) if ok else None, "USD", lit, "s1", ADAPTER, "html_table", obs,
                                   {"label": "Replacement Filter"}, lit, conditions={"filter_stage": "set", "price_basis": bs},
                                   status="known" if ok else "unknown"))
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "rows": len(rows), "unmapped": {k: v for k, v in rows.items() if k not in used}}
    return pr


if __name__ == "__main__":
    _run.main(WinixAirPurifiers())
