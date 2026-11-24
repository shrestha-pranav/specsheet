#!/usr/bin/env python3
"""Title -> product matcher over the published static dataset (docs/api/v1). Precision first: no answer beats a wrong answer.

    python3 scripts/match.py "Anker 735 Charger (Nano II 65W) GaN 3-port $25.99 at Amazon" [--category chargers] [--json]
    from match import match; match(title, category=None) -> [ {id, category, brand, name, basis, confidence, evidence} ]
    python3 scripts/match.py --build-aliases [--api docs/api/v1]      (build.py calls write_aliases() after publishing)

Inputs (trusted catalogue only, never preview): <cat>/index*.json rows (id, brand, name, identifier keys), lookup/identifiers.json
(scheme:VALUE -> ids for mfr_model / mfr_sku / mtm / gtin), redirects.json, and lookup/aliases.json (compact: normalised alias phrase -> ids, only
phrases that differ from the published name: maker marketing names, label models, retail titles, and the retired v0 gan-chargers pilot names
mapped through its id redirects).

Match bases, strongest first. A basis is used only when exactly ONE product survives it; otherwise the next basis is tried, and two products
surviving the best basis that matched anything means 'ambiguous' -> no candidates (the reason is in `diagnostics`).
  exact_model_number   a title token equals a published maker identifier (mfr_model / mtm / mfr_sku, separators ignored) or a valid GTIN.
                       Pure-digit tokens (UGREEN item 15202) count only when the title also names that product's brand.
  exact_alias          every token of a published name or alias phrase is in the title.
  brand_marketing_name the title names the product's brand and every DISTINCTIVE token of one of its phrases (name minus brand and generic words,
                       at least two tokens, one of them carrying a digit or a model word) is in the title.
Guards (any basis): the brand named in the title must be the product's brand; a category the title names (SSD, TV, monitor, power bank,
charger...) must be the product's category; attributes printed on both sides must agree (wattage W, capacity TB/GB/mAh, screen inches, port
count); and variant tokens the title asserts (marketing numbers like 735/737, generations II/3, Pro/Max/Ultra/Mini/Plus...) must appear in the
product's own phrases. This is what separates Anker 735 from 737 and Nano II from Nano 3.
"""
import argparse, functools, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "docs" / "api" / "v1"
ALIASES = "lookup/aliases.json"
ALIAS_KINDS = ("marketing_name", "label_model", "retail_title")
BRAND_ALIASES = {"western digital": ["wd", "wd black", "wd_black", "sandisk", "western digital"], "team": ["teamgroup", "team group", "t-force", "t force"],
                 "tp_link": ["tp-link", "tp link", "tplink"], "native_union": ["native union"], "hyper": ["hyperjuice", "hyper", "targus"],
                 "goal_zero": ["goal zero"], "lg": ["lg"], "hp": ["hp"], "msi": ["msi"], "iniu": ["iniu"], "ecoflow": ["ecoflow", "eco flow"],
                 "irobot": ["irobot", "roomba"], "cuktech": ["cuktech"], "choetech": ["choetech"], "tripplite": ["tripp lite", "tripplite", "eaton tripp lite"]}
GENERIC = set("""charger chargers wall usb c a type port ports fast charging charge adapter adapters power block plug with and for the of in to gan pd
3.0 3.1 delivery compact foldable travel desktop station brick cube laptop phone iphone samsung galaxy pixel ipad macbook new official edition
black white gray grey blue silver green pink red purple beige graphite space cream starlight portable ssd internal external solid
state drive nvme pcie m.2 m 2 sata 2.5 gen4 gen5 gen3 x4 tv smart led uhd 4k qled oled hdr monitor display gaming inch class series model
retractable cable built included kit set w wh v a""".split())
MODIFIERS = set("ii iii iv v vi pro max plus ultra mini lite air slim prime neo se elite evo duo trio go flex next uno core nano".split())
CATS = [("power-banks", r"power ?bank|portable charger|battery pack|magsafe battery"), ("power-stations", r"power station|solar generator"),
        ("chargers", r"\bcharger\b|charging station|power adapter|wall adapter|\bgan\b"), ("ssds", r"\bssd\b|nvme|solid state"),
        ("monitors", r"\bmonitor\b"), ("tvs", r"\btv\b|television|\bqled\b|\boled tv\b|roku tv|google tv|fire tv"),
        ("laptops", r"\blaptop\b|notebook|chromebook|thinkpad|ideapad|zenbook|vivobook"), ("routers", r"router|mesh wi-?fi|wifi system"),
        ("robot-vacuums", r"robot vacuum|robovac|roomba"), ("air-purifiers", r"air purifier"), ("power-strips", r"surge protector|power strip")]
RETAILERS = r"amazon|best ?buy|walmart|target|newegg|b&h|costco|ebay|woot|micro center|bj'?s|sam'?s club|home depot|lowe'?s|staples|adorama"


# ---------------------------------------------------------------- text
def clean_title(t):
    t = t or ""
    t = re.sub(r"\$\s?\d[\d,]*(?:\.\d{1,2})?|\b\d{1,3}%\s*off\b|\bsave\s+\$?\d+\b", " ", t, flags=re.I)
    t = re.sub(r"(?i)\s(?:at|@|from|via)\s+(?:" + RETAILERS + r")\b.*$", " ", t)
    t = re.sub(r"(?i)\b(?:deal|lowest price|all-time low|price drop|clearance|coupon|w/ code|with code|free shipping|prime members?)\b", " ", t)
    return t


def tokens(s):
    s = (s or "").lower().replace("″", '"').replace("”", '"').replace("“", '"').replace("’", "'")
    s = re.sub(r"(\d)\s*-?\s*ports?\b", r"\1port", s)
    s = re.sub(r"(\d)\s*-?\s*(?:inch(?:es)?|in\b|\"|-in\b)", r"\1in", s)
    s = re.sub(r"(\d)\s*-?\s*(?:class)\b", r"\1in", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(w|tb|gb|mah|wh|hz)\b", r"\1\2", s)
    s = re.sub(r"\b(\d{1,2})k\s*mah\b|\b(\d{1,2})k\b(?=.*\b(?:power ?bank|mah)\b)", lambda m: f"{m[1] or m[2]}000mah", s)
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", s)


def attrs(toks):
    a = {}
    for t in toks:
        for k, rx in (("w", r"(\d+(?:\.\d+)?)w"), ("tb", r"(\d+(?:\.\d+)?)tb"), ("gb", r"(\d+)gb"), ("mah", r"(\d+)mah"), ("in", r"(\d{2,3})in"), ("port", r"(\d)port")):
            m = re.fullmatch(rx, t)
            if m:
                a.setdefault(k, set()).add(float(m[1]))
    if "gb" in a:          # 2000GB == 2TB
        a.setdefault("tb", set()).update(x / 1000 for x in a["gb"] if x >= 1000)
    return a


def norm_id(v):
    return re.sub(r"[\s.\-]", "", str(v).upper())


def model_tokens(title):
    """Identifier-shaped tokens from the raw title: letters+digits (PA-C4, MZ-V9P2T0B/AM, 27GP850-B, 65QM850G), 5+ digit runs, GTINs."""
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Za-z0-9][A-Za-z0-9\-./#]{2,}[A-Za-z0-9])(?![A-Za-z0-9])", title):
        t = m[1].strip("./-")
        if re.search(r"\d", t) and (re.search(r"[A-Za-z]", t) or len(t) >= 5):
            out.append(t)
            if "/" in t:
                out.append(t.split("/")[0])
            nxt = re.match(r"\s+([A-Za-z]{2,6})\b(?:\s+([A-Za-z]{2,6})\b)?", title[m.end():])   # 'RT-AX88U Pro', 'Archer AX55 Pro': multi-word models
            if nxt:
                out.append(f"{t} {nxt[1]}")
                if nxt[2]:
                    out.append(f"{t} {nxt[1]} {nxt[2]}")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- catalogue
class Catalogue:
    def __init__(self, api=API):
        api = Path(api)
        self.api = api
        cats = json.loads((api / "categories.json").read_text())
        self.products, self.brand_names = {}, {}
        for c in cats:
            if not c.get("index") or c.get("demo"):
                continue
            for p in c["index"]:
                for r in json.loads((api / p).read_text()):
                    if r.get("kind") in ("family", "revision"):
                        continue
                    self.products[r["id"]] = {"id": r["id"], "category": c["id"], "brand": r.get("brand") or "", "brand_id": r.get("brand_id") or "",
                                              "name": r.get("name") or "", "ids": r.get("ids") or [], "phrases": [r.get("name") or ""]}
                    bid = r.get("brand_id") or ""
                    for n in {bid.replace("_", " "), (r.get("brand") or "").lower()} | set(BRAND_ALIASES.get(bid, [])):
                        n = " ".join(tokens(n))
                        if n and len(n) >= 2:
                            self.brand_names.setdefault(n, set()).add(bid)
        self.ident = json.loads((api / "lookup" / "identifiers.json").read_text())
        al = api / ALIASES
        self.aliases = json.loads(al.read_text()).get("aliases", {}) if al.exists() else {}
        for phrase, ids in self.aliases.items():
            for i in ids:
                if i in self.products:
                    self.products[i]["phrases"].append(phrase)
        for p in self.products.values():
            toks = set()
            for ph in p["phrases"]:
                toks |= set(tokens(ph))
            for k in p["ids"]:
                toks |= set(tokens(k.split(":", 1)[-1]))
            p["toks"] = toks
            p["btoks"] = set(tokens(p["brand"])) | {t for n, b in self.brand_names.items() if p["brand_id"] in b for t in n.split()}
        self.mod_by_brand = {}
        for p in self.products.values():      # variant words a brand actually uses (a 'Pro' in a title only contradicts brands that sell Pros)
            self.mod_by_brand.setdefault(p["brand_id"], set()).update(t for t in p["toks"] if t in MODIFIERS)

    def brands_in(self, toks):
        s = " " + " ".join(toks) + " "
        return {b for n, bs in self.brand_names.items() if f" {n} " in s for b in bs}


@functools.lru_cache(maxsize=4)
def catalogue(api=str(API)):
    return Catalogue(api)


def title_category(text):
    for cat, rx in CATS:
        if re.search(rx, text, re.I):
            return cat
    return None


# ---------------------------------------------------------------- matching
def is_multipack(text):
    return bool(re.search(r"(?i)\b(?:[2-9]|two|three|four)\s*-?\s*(?:pack|pk|count|ct)\b|\bpack of [2-9]\b|\b[2-9]\s*x\s+(?!usb)", text))


def _guards(p, ttoks, tattrs, brands, tcat, cat, C, attributes=True, multipack=False):
    """-> reason string if the product is ruled out, else None. attributes=False (exact identifier hits): printed attributes and variant tokens
    are not used to reject, because the identifier is stronger evidence than the catalogue's display name (see attr_conflict)."""
    if cat and p["category"] != cat:
        return "category filter"
    if multipack and not re.search(r"(?i)pack|\b\d+\s*-?\s*count\b", " ".join(p["phrases"])):
        return "title is a multipack listing (a package), the product is a single unit"
    if brands and p["brand_id"] not in brands:
        return f"title names brand {sorted(brands)}"
    if tcat and p["category"] != tcat:
        return f"title names category {tcat}"
    if not attributes:
        return None
    return attr_conflict(p, ttoks, tattrs, C) or variant_conflict(p, ttoks, C)


def attr_conflict(p, ttoks, tattrs, C):
    pa = attrs(p["toks"])
    for k in ("w", "tb", "mah", "in", "port"):
        if k in pa and k in tattrs and not (pa[k] & tattrs[k]):
            return f"{k} differs ({sorted(pa[k])} vs title {sorted(tattrs[k])})"
    if "gb" in pa and "gb" in tattrs and not (pa["gb"] & tattrs["gb"]) and "tb" not in pa:
        return "capacity differs"
    return None


def variant_conflict(p, ttoks, C):
    mods = C.mod_by_brand.get(p["brand_id"], set())       # variant words this brand uses anywhere in the catalogue
    extra = {t for t in ttoks if t not in p["toks"] and (re.fullmatch(r"\d{3}", t) or t in ("ii", "iii", "iv") or (t in MODIFIERS and t in mods))}
    if extra:
        return f"title asserts {sorted(extra)}, which this product's names do not carry"
    return None


def match(title, category=None, api=None, diagnostics=None):
    C = catalogue(str(api or API))
    raw = clean_title(title)
    ttoks = tokens(raw)
    tset = set(ttoks)
    tattrs = attrs(ttoks)
    brands = C.brands_in(ttoks)
    tcat = title_category(raw)
    mp = is_multipack(raw)
    diag = diagnostics if diagnostics is not None else {}
    diag.update({"brands": sorted(brands), "title_category": tcat})
    out = []

    def finish(cands, basis, conf, ev):
        return [{"id": p["id"], "category": p["category"], "brand": p["brand"], "name": p["name"], "basis": basis, "confidence": conf,
                 "evidence": ev[p["id"]]} for p in cands]

    # 1. exact model number / identifier
    hits, rej = {}, {}
    for tok in model_tokens(raw):
        nv = norm_id(tok)
        keys = [f"{s}:{nv}" for s in ("mfr_model", "mtm", "mfr_sku")]
        if re.fullmatch(r"\d{8}|\d{12,14}", nv):
            keys.append(f"gtin:{nv.zfill(14)}")
        ids = {i for k in keys for i in C.ident.get(k, [])} | {i for i in C.aliases.get(" ".join(tokens(tok)), []) if re.search(r"\d", tok)
                                                              and len(tokens(tok)) == 1}
        for i in ids:
            p = C.products.get(i)
            if not p:
                continue
            if nv.isdigit() and len(nv) < 8 and p["brand_id"] not in brands:
                rej[i] = f"bare number {tok} without the brand"; continue
            why = _guards(p, ttoks, tattrs, brands, tcat, category, C, attributes=False, multipack=mp)
            nxt = re.match(r"\s+([A-Za-z]+)", raw[raw.find(tok) + len(tok):]) if tok in raw else None
            if not why and nxt and nxt[1].lower() in MODIFIERS | {"ii", "iii"} and nxt[1].lower() not in p["toks"]:
                why = f"the word after {tok} ('{nxt[1]}') names a variant this product does not carry"     # 'RT-AX88U Pro' is not RT-AX88U
            if why:
                rej[i] = why; continue
            hits.setdefault(i, []).append(tok)
    if hits:
        diag["model_hits"] = hits
        if len(hits) == 1:
            i = next(iter(hits))
            conf = 0.97 if C.products[i]["brand_id"] in brands else 0.9
            ev = {"tokens": hits[i]}
            if (c := attr_conflict(C.products[i], ttoks, tattrs, C)):
                conf, ev["conflict"] = round(conf - 0.15, 2), f"identifier matches but the catalogue name disagrees: {c}"
            return finish([C.products[i]], "exact_model_number", conf, {i: ev})
        diag["ambiguous"] = f"identifier tokens name {len(hits)} products"
        return []
    if rej:
        diag["model_rejected"] = rej
    # 2/3. alias phrases
    full, part = {}, {}
    for p in C.products.values():
        if category and p["category"] != category:
            continue
        if brands and p["brand_id"] not in brands:
            continue
        best_full = best_part = None
        for ph in p["phrases"]:
            pt = [t for t in tokens(ph)]
            if not pt:
                continue
            if set(pt) <= tset and len(set(pt) - GENERIC - p["btoks"]) >= 1:
                n = len(set(pt))
                best_full = max(best_full or 0, n)
            dist = set(pt) - GENERIC - p["btoks"]
            if brands and len(dist) >= 2 and dist <= tset and any(re.search(r"\d", t) or t in MODIFIERS for t in dist):
                best_part = max(best_part or 0, len(dist))
        if best_full is None and best_part is None:
            continue
        why = _guards(p, ttoks, tattrs, brands, tcat, category, C, multipack=mp)
        if why:
            diag.setdefault("alias_rejected", {})[p["id"]] = why; continue
        if best_full:
            full[p["id"]] = best_full
        if best_part:
            part[p["id"]] = best_part
    for basis, pool, conf in (("exact_alias", full, 0.88), ("brand_marketing_name", part, 0.72)):
        if not pool:
            continue
        top = max(pool.values())
        best = [i for i, n in pool.items() if n == top]
        if len(best) == 1:
            i = best[0]
            return finish([C.products[i]], basis, conf if top >= 3 else round(conf - 0.1, 2), {i: {"matched_tokens": top}})
        diag["ambiguous"] = f"{basis}: {len(best)} products tie ({', '.join(sorted(best)[:5])})"
        return []
    return out


# ---------------------------------------------------------------- aliases.json (called from build.py)
def write_aliases(api=API, legacy=()):
    """lookup/aliases.json: normalised phrase -> [ids] for every trusted product alias that differs from its published name, plus `legacy`
    [(old id, old name)] from the retired v0 pilot resolved through redirects.json (only when it lands on exactly one published product).
    Kept compact: phrases equal to the name are not repeated (the matcher reads names from the index rows)."""
    api = Path(api)
    cats = json.loads((api / "categories.json").read_text())
    names, ali = {}, {}
    for c in cats:
        if not c.get("index") or c.get("demo"):
            continue
        for p in c["index"]:
            for r in json.loads((api / p).read_text()):
                names[r["id"]] = " ".join(tokens(r.get("name") or ""))
        for f in sorted((api / c["id"] / "products").glob("*.json")):
            d = json.loads(f.read_text())
            if d["id"] not in names:
                continue
            for a in d.get("aliases") or []:
                if a.get("kind") not in ALIAS_KINDS or (a["kind"] == "label_model" and not re.search(r"\d", a["text"])):
                    continue
                t = " ".join(tokens(a["text"]))
                if t and t != names[d["id"]]:
                    ali.setdefault(t, set()).add(d["id"])
    red = json.loads((api / "redirects.json").read_text()) if (api / "redirects.json").exists() else {}
    n_leg = 0
    for old, name in legacy:
        tgt = [old] if old not in red else red[old].get("replaced_by") or []
        if len(tgt) == 1 and tgt[0] in names:
            t = " ".join(tokens(re.sub(r"[\[\]]", " ", name)))
            if t and t != names[tgt[0]]:
                ali.setdefault(t, set()).add(tgt[0]); n_leg += 1
    doc = {"format": "specsheet.aliases/1", "note": "normalised alias phrase -> trusted product ids; phrases equal to the product name are omitted. "
           "Built by scripts/match.py write_aliases().", "aliases": {k: sorted(v) for k, v in sorted(ali.items())}}
    p = api / ALIASES
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    return {"phrases": len(ali), "legacy": n_leg, "bytes": p.stat().st_size}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("title", nargs="?")
    ap.add_argument("--category")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--api", default=str(API))
    ap.add_argument("--build-aliases", action="store_true")
    a = ap.parse_args()
    if a.build_aliases:
        print(json.dumps(write_aliases(a.api)))
        return
    if not a.title:
        ap.error("title required")
    diag = {}
    res = match(a.title, a.category, a.api, diag)
    if a.json:
        print(json.dumps({"title": a.title, "candidates": res, "diagnostics": diag}, indent=1, ensure_ascii=False, default=sorted))
    else:
        if not res:
            print(f"no match ({diag.get('ambiguous') or 'nothing safe'})")
        for r in res:
            print(f"{r['id']}  [{r['category']}]  {r['name']}  basis={r['basis']} confidence={r['confidence']}")


if __name__ == "__main__":
    main()
