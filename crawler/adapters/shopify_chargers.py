#!/usr/bin/env python3
"""Shopify-store USB charger adapters (contract ARCHITECTURE 15.5), category chargers. One module, one class per US store:
UGREEN (us.ugreen.com), INIU (iniushop.com), CUKTECH (www.cuktech.com), Satechi (satechi.net), SHARGE (sharge.com), mophie (www.mophie.com),
AUKEY (www.aukey.com), HyperJuice (www.hypershop.com), Native Union (www.nativeunion.com), Plugable (plugable.com), Nekteck (www.nekteck.com),
Choetech (www.choetech.com). New module (not shopify_powerbanks*) so the audited power-bank parser fingerprints do not move; the PDO/port model
is the shared _powerbank one, the charger semantics live in _charger.

discover : {base}/products.json?limit=250&page=N (public Shopify catalogue; robots allow /products). Kept: titles that name a wall/desktop/car
           charger or charging station; dropped: wireless/magnetic/Qi pads and stands, power banks (incl. 'portable charger' hybrids), cables, hubs,
           bundles ('+', 'Bundle', 'N-Pack', kits, gift sets), refurbished, non-US plug listings (EU/UK/AU/JP-only titles). One Ref per handle.
fetch    : product page HTML + {base}/products/<handle>.json, one gzip JSON blob {"page", "product"} (2 requests, 1 req/s per host).
parse    : pure, in _charger.parse_store(): labelled spec rows from the page (tables, dt/dd, 'Label: value' lines in the spec section), never prose.
Identity : per brand (model_of): the maker's printed model number when the page has one, else the brand's documented SKU stem rule. Pages
           without a model are absences (no entity). Colour/region SKUs are mfr_sku aliases.
"""
import gzip, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _charger as G
import _run

VERSION = 2       # v2: r7 shared _powerbank (energy_basis pairs, case-insensitive Wh); charger rules unchanged
CATEGORIES = {"chargers"}
DELAY = 1.0
CHG = re.compile(r"charger|charging station|charging hub|power adapter|wall adapter|power delivery adapter|\bGaN\b.*\d+\s*W", re.I)
NOT = re.compile(r"wireless|magsafe|magnetic|\bqi2?\b|qi-|power ?bank|portable (?:wall )?charger|battery|\bcables?\b(?! management)|hub\b|stand\b|\bpad\b|watch|"
                 r"airpods|case\b|bundle|\+|\b\d-?pack\b|pack\)|\bkit\b|gift|solar|alternator|generator|\bev\b|holder|mount|earbud|refurb|"
                 r"replacement|cooling fan|sticker|protection plan|power strip|surge|outlet extender|organizer|vision pro|ipad|lightning to|"
                 r"hdmi|ethernet|multiport|card", re.I)
NON_US = re.compile(r"\b(?:EU|UK|AU|JP|KR|IN)\s*(?:/\s*(?:EU|UK|AU|JP))*\s*(?:Plug|Version)\b|\bEU\b(?!.*\bUS\b)|European|British", re.I)


class _ShopC:
    id = source_id = base = brand = brand_name = None
    version, categories = VERSION, CATEGORIES
    extra_not = None

    def __init__(self):
        self.store = C.BlobStore(self.source_id)
        self.adapter = f"{self.id}@{self.version}"

    def keep(self, p):
        t, h = p.get("title") or "", p.get("handle") or ""
        if not CHG.search(t) or NOT.search(t) or NOT.search(h.replace("-", " ")) or NON_US.search(t):
            return False
        return not (self.extra_not and (re.search(self.extra_not, t, re.I) or re.search(self.extra_not, h, re.I)))

    def discover(self, checkpoint, net):
        refs, page = [], 1
        while page <= 12:
            r = net.get(f"{self.base}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery(refs, False, f"products.json page {page}: {getattr(r, 'status_code', r)}", {"page": page})
            ps = r.json().get("products") or []
            if not ps:
                break
            for p in ps:
                if self.keep(p):
                    refs.append(C.Ref(self.source_id, p["handle"], f"{self.base}/products/{p['handle']}", {"title": p.get("title")}))
            page += 1
        return C.Discovery(refs, True, None, {"products": len(refs), "pages": page - 1})

    def fetch(self, ref, prior, net):
        now = time.strftime("%FT%TZ", time.gmtime())
        r = net.get(ref.url, DELAY)
        if r is None or isinstance(r, str) or r.status_code != 200:
            st = r if (r is None or isinstance(r, str)) else r.status_code
            s = C.Snapshot("sha256:", ref, st or "breaker", now, ref.url, {})
            self.store.append(s, self.adapter, ".json.gz")
            return s
        j = net.get(ref.url + ".json", DELAY)
        prod = j.json().get("product") if (hasattr(j, "status_code") and j.status_code == 200) else None
        body = json.dumps({"page": r.text, "product": prod}).encode()
        s = C.Snapshot(self.store.put(gzip.compress(body, 6, mtime=0), ".json.gz"), ref, 200, now, r.url,
                       {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")})
        self.store.append(s, self.adapter, ".json.gz")
        return s

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return G.parse_store(self, snap, d["page"], d.get("product") or {})

    # ---- identity rules (override per brand). rows = labelled spec rows {label: value}; skus = variant SKUs; title = product title
    def model_of(self, rows, skus, title, handle):
        return None, None


def _row(rows, *labels):
    for lab in labels:
        for k, v in rows.items():
            if k.lower() == lab.lower() and v:
                return v
    return None


def _one(cands):
    c = list(dict.fromkeys(x for x in cands if x))
    return c[0] if len(c) == 1 else None


class UgreenChargers(_ShopC):
    id, source_id, base, brand, brand_name = "ugreen_chargers", "ugreen-us-chargers", "https://us.ugreen.com", "ugreen", "UGREEN"
    extra_not = r"star rail|honkai"        # licensed editions: same hardware as a base item number, not provable from the page (identity.md)

    def model_of(self, rows, skus, title, handle):
        # UGREEN's US store prints the 5-digit item number (SKU 'Model' rows when present carry the label model CD244 etc.: kept as alias)
        its = [s for s in skus if re.fullmatch(r"\d{5}A?", s)]
        m = _one(its)
        return (m, "item number (variant SKU)") if m else (None, f"item numbers {its or skus}")


class IniuChargers(_ShopC):
    id, source_id, base, brand, brand_name = "iniu_chargers", "iniu-us-chargers", "https://iniushop.com", "iniu", "INIU"

    def model_of(self, rows, skus, title, handle):
        p = _row(rows, "Product Model", "Model")
        if p and (m := re.match(r"^([A-Z]{1,2}-?\d{2,4}(?:-E\d)?)\b", p.strip().upper())):
            return m[1], "printed Model row"
        rx = r"D01-([A-Z]{1,2}\d{2,4}(?:-E\d)?)"          # D01-A11-E1-US-BK -> A11-E1; multipack SKUs (-2P-) and bare numbers (D01-1847) are not models
        toks = {re.match(rx, s.upper())[1] for s in skus if re.match(rx, s.upper()) and not re.search(r"-[2-9]P(?:-|$)", s.upper())}
        m = _one(sorted(toks))
        return (m, "D01- SKU stem") if m else (None, f"SKU stems {sorted(toks)}")


class CuktechChargers(_ShopC):
    id, source_id, base, brand, brand_name = "cuktech_chargers", "cuktech-us-chargers", "https://www.cuktech.com", "cuktech", "CUKTECH"

    def model_of(self, rows, skus, title, handle):
        p = _row(rows, "Model", "Product Model")
        if p and (m := re.match(r"^([A-Z]{1,3}\d{2,4}[A-Z]{0,3})\b", p.strip().upper())):
            return m[1], "printed Model row"
        return None, "no Model row"


class SatechiChargers(_ShopC):
    id, source_id, base, brand, brand_name = "satechi_chargers", "satechi-us-chargers", "https://satechi.net", "satechi", "Satechi"

    def model_of(self, rows, skus, title, handle):
        # ST-UC165GM / ST-UC165GM-EU / ST-COTG45Y-US: region suffix stripped; colour letters (Y/P/B/S, K/W/R) are configurations of one model
        st = set()
        for s in skus:
            s = re.sub(r"-(US|EU|UK|AU|JP|KR)$", "", s.upper())
            st.add(s)
        m = _one(sorted(st))
        if m:
            return m, "SKU (region suffix stripped)"
        stems = {s[:-1] for s in st}         # colour letter = the last character (ST-COTG45Y / P / B / S, ST-TCPDCCM / S)
        m = _one(sorted(stems)) if len({len(s) for s in st}) == 1 and len(st) > 1 else None
        return (m, "SKU stem (colour letter stripped)") if m else (None, f"SKUs {sorted(st)}")


class ShargeChargers(_ShopC):
    id, source_id, base, brand, brand_name = "sharge_chargers", "sharge-us-chargers", "https://sharge.com", "sharge", "SHARGE"

    def model_of(self, rows, skus, title, handle):
        p = _row(rows, "Product Model", "Prodcut Model", "Model")
        if p and re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,20}", p.strip().upper()):
            return p.strip().upper(), "printed Product Model row"
        return None, "no single Product Model row"


class MophieChargers(_ShopC):
    id, source_id, base, brand, brand_name = "mophie_chargers", "mophie-us-chargers", "https://www.mophie.com", "mophie", "mophie"

    def model_of(self, rows, skus, title, handle):
        pn = sorted({s for s in skus if re.fullmatch(r"\d{9}", s)})
        m = _one(pn)
        return (m, "9-digit part number (no model printed)") if m else (None, f"part numbers {pn}")


class AukeyChargers(_ShopC):
    id, source_id, base, brand, brand_name = "aukey_chargers", "aukey-us-chargers", "https://www.aukey.com", "aukey", "AUKEY"
    extra_not = r"PA-B1[345]\b.*PA-B1[345]\b"    # one page for several models

    def model_of(self, rows, skus, title, handle):
        ms = list(dict.fromkeys(re.findall(r"\b((?:PA|CC)-[A-Z]?\d{1,2}[A-Z]?)\b", title.upper())))
        p = _row(rows, "Model", "Model Number")
        if p and (pm := re.match(r"^((?:PA|CC)-[A-Z]?\d{1,2}[A-Z]?)\b", p.strip().upper())):
            if not ms or ms == [pm[1]]:
                return pm[1], "printed Model row"
        m = _one(ms)
        return (m, "model number in the maker's title (PA-/CC-)") if m else (None, f"title models {ms}")


class HyperChargers(_ShopC):
    id, source_id, base, brand, brand_name = "hyper_chargers", "hyper-us-chargers", "https://www.hypershop.com", "hyper", "HyperJuice (Targus)"

    def model_of(self, rows, skus, title, handle):
        # HJ1402NA: NA = North America plug; HJ1202BUNA = colour BU + NA; HJ1002WHWWGL = colour WH + worldwide kit WWGL. Model = HJ + 4 digits.
        st = sorted({re.match(r"(HJ\d{4})", s.upper())[1] for s in skus if re.match(r"HJ\d{4}", s.upper())})
        m = _one(st)
        return (m, "HJ#### stem of the variant SKUs") if m else (None, f"stems {st}")


class NativeUnionChargers(_ShopC):
    id, source_id, base, brand, brand_name = "nativeunion_chargers", "nativeunion-us-chargers", "https://www.nativeunion.com", "native_union", "Native Union"

    def model_of(self, rows, skus, title, handle):
        st = sorted({re.sub(r"-(US|EU|UK|INT|AU)$", "", re.sub(r"-(BLK|WHT|SAN|SLA|GRN|BLU|PNK|ZEB)(?=-|$)", "", s.upper())) for s in skus if s.upper().startswith("FAST-")})
        m = _one(st)
        return (m, "FAST- SKU stem (colour + region stripped)") if m else (None, f"stems {st}")


class PlugableChargers(_ShopC):
    id, source_id, base, brand, brand_name = "plugable_chargers", "plugable-us-chargers", "https://plugable.com", "plugable", "Plugable"
    extra_not = r"\bps\d+-|power strip|outlet"

    def model_of(self, rows, skus, title, handle):
        m = _one([s.upper() for s in skus if re.fullmatch(r"PS-\d{1,3}C\d?[A-Z]?", s.upper())])
        return (m, "model SKU (colour letter part of the maker model)") if m else (None, f"SKUs {skus}")


class NekteckChargers(_ShopC):
    id, source_id, base, brand, brand_name = "nekteck_chargers", "nekteck-us-chargers", "https://www.nekteck.com", "nekteck", "Nekteck"

    def model_of(self, rows, skus, title, handle):
        p = _row(rows, "Model", "Model Number", "Item model number")
        if p and re.fullmatch(r"[A-Z0-9][A-Z0-9-]{3,24}", p.strip().upper()):
            return p.strip().upper(), "printed Model row"
        m = _one([re.sub(r"-SPNK$", "", s.upper()) for s in skus])
        return (m, "SKU (store suffix -SPNK stripped)") if m else (None, f"SKUs {skus}")


class ChoetechChargers(_ShopC):
    id, source_id, base, brand, brand_name = "choetech_chargers", "choetech-us-chargers", "https://www.choetech.com", "choetech", "CHOETECH"

    def keep(self, p):
        t = p.get("title") or ""
        return super().keep(p) and not re.search(r"\bEU\b|\bUK\b", t) or (super().keep(p) and re.search(r"\bUS\b", t) is not None)

    def model_of(self, rows, skus, title, handle):
        ms = list(dict.fromkeys(re.findall(r"\b((?:PD|Q|C|GMTC)\d{3,4}[A-Z]?(?:-[A-Z]{1,2}\d?)?)\b", title.upper())))
        ms = [x for x in ms if not re.fullmatch(r"C\d{3}", x) or x.startswith("C0")]
        m = _one(ms)
        return (m, "model number in the maker's title (PD####)") if m else (None, f"title models {ms}")


ALL = (UgreenChargers, IniuChargers, CuktechChargers, SatechiChargers, ShargeChargers, MophieChargers, AukeyChargers, HyperChargers,
       NativeUnionChargers, PlugableChargers, NekteckChargers, ChoetechChargers)

if __name__ == "__main__":
    which = {c.source_id: c for c in ALL}
    src = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in which else None
    if not src:
        raise SystemExit("usage: shopify_chargers.py <source-id> discover|fetch|parse  (" + ", ".join(which) + ")")
    _run.main(which[src]())
