#!/usr/bin/env python3
"""CPSC recalls overlay v1 (contract ARCHITECTURE 15.5): safety.recall for every model-importer category. A2-safe r12.

Source   : the CPSC Recalls REST API https://www.saferproducts.gov/RestWebServices/Recall?format=json (US CPSC; robots.txt 404 = no rules;
           CPSC Privacy and Security Notice: web text is public information, freely copy/distribute, credit CPSC, never imply endorsement;
           data/source-policy.yaml www.saferproducts.gov). Recall notice URLs point at www.cpsc.gov/Recalls/<year>/<slug> (never fetched here).
pull     : `cpsc_recalls.py pull` = one GET per recall year (RecallDateStart/RecallDateEnd), each stored as a snapshot `_year_YYYY` in the
           SHARED fetch store raw/cpsc-recalls (not a registry source). Paced through crawl.Net (policy + robots on every hop), DELAY 2 s.
           A year page already pulled today is reused; past years are reused unless --refresh.
discover : (per category source cpsc-recalls-<cat>, no network) read the latest year pages, keep recalls whose product text names this
           category's product type (TYPE_RX) and whose firm / title / product text names a brand that already has entities in this category
           (BRANDS from state/specsheet.sqlite, recorded in the checkpoint), and extract the model numbers the notice prints (MODEL_*). One
           ref per (brand, model, recall number); hints carry the recall number and whether an entity with that exact model exists.
           The recall object is copied verbatim (canonical JSON) into the category store as that ref's blob: parse stays pure.
parse    : pure. mfr_model = the model as the notice prints it (issuer = brand). claim safety.recall (text, 'CPSC <no> (<date>): <hazard>')
           with locator recall number; plus safety.recall_id / safety.recall_date / safety.recall_remedy / safety.recall_url and
           gen.record_kind. Coordinator ruling r12: an exact-model match enriches the existing entity (gen.record_kind is NOT emitted then, so
           the maker's record kind is untouched); with no entity the ref mints a recall-only record whose ONLY facts are identity + recall facts,
           flagged gen.record_kind = recall_only (excluded from every preset population, docs/presets.json / scripts/presets.py).
Rules    : a recall applies only to model numbers the notice names; nothing is extended by pattern, prefix or family. A notice naming no
           model number produces nothing (counted). A notice naming several brands, or with 'Commercial' in its title, never
           mints a record. Absence of a recall is never 'no recall': nothing here writes a negative.
Usage    : python3 -I crawler/adapters/cpsc_recalls.py pull [--refresh]
           python3 -I crawler/adapters/cpsc_recalls.py <category> discover; ... <category> fetch --refresh   (fetch is local: --refresh
           re-copies every ref, so a model that gained a maker/certifier record loses its recall_only flag on the next import)
"""
import json, re, sqlite3, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
from _contract import Ref, Discovery, ParseResult, claim  # noqa
import _run

ID, VERSION = "cpsc_recalls", 1
ADAPTER = f"{ID}@{VERSION}"
SHARED = "cpsc-recalls"
API = "https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart={y}-01-01&RecallDateEnd={y}-12-31"
DELAY = 2.0
FIRST_YEAR = 2005
STAGE = "feed"
KEYS = ("safety.recall", "safety.recall_id", "safety.recall_date", "safety.recall_remedy", "safety.recall_url", "gen.record_kind")

# Product type per category, in PRIORITY order: a recall belongs to the FIRST category whose pattern its title or product names match
# ('Laptop Power Banks' is a power bank, 'Laptop AC Adapters' a charger, 'Refrigerator-Freezers' a refrigerator).
TYPES = [
    ("power-stations", r"portable power stations?|power stations?\b|solar generators?"),
    ("power-banks", r"power ?banks?|portable (?:wireless )?chargers?|portable batter(?:y|ies) (?:packs?|chargers?)"),
    ("robot-vacuums", r"robot(?:ic)? vacuums?|robot(?:ic)? (?:floor )?cleaners?"),
    ("air-purifiers", r"air purifiers?|air cleaners?"),
    ("dehumidifiers", r"dehumidifiers?"),
    ("room-air-conditioners", r"(?:room|window|portable|through-the-wall) air conditioners?"),
    ("dishwashers", r"dishwashers?"),
    ("refrigerators", r"refrigerators?|refrigerator-freezers?|\bfridges?\b|minifridges?|mini-fridges?"),
    ("freezers", r"(?:chest|upright|deep) freezers?|\bfreezers\b"),
    ("clothes-washers", r"washing machines?|clothes washers?|(?:front|top)[- ]load(?:ing)? washers?|\bwashers\b(?! and dryers? sold)"),
    ("clothes-dryers", r"clothes dryers?|(?:gas|electric) dryers?|(?:front|top)[- ]load(?:ing)? dryers?"),
    ("chargers", r"(?:wall|usb|usb-c|phone|travel|fast|wireless|gan) chargers?|charging (?:adapters?|bricks?|blocks?|pads?|stands?)|(?:power|ac|laptop) adapters?"),
    ("smart-home", r"smart (?:plugs?|bulbs?|switch(?:es)?|locks?|thermostats?|light strips?|outlets?|sensors?)|video doorbells?|zigbee|matter-certified"),
    ("routers", r"wi-?fi routers?|wireless routers?|mesh (?:wi-?fi|routers?|systems?)"),
    ("monitors", r"(?:computer|pc|gaming|lcd|led|desktop) monitors?"),
    ("tvs", r"televisions?|\btvs?\b|led-tvs?"),
]
TYPE_RX = {c: re.compile(rx, re.I) for c, rx in TYPES}
# Firm-name spellings a brand id does not spell itself. Spelling only: no corporate-parent folding (Haier != GE brand).
BRAND_EXTRA = {"ge": ["General Electric", "GE Appliances", "GE-brand", "GE Profile", "GE Monogram"], "lg": ["LG Electronics"],
               "tp_link": ["TP-Link"], "goal_zero": ["Goal Zero"], "fisher_paykel": ["Fisher & Paykel", "Fisher and Paykel"],
               "black_decker": ["Black+Decker", "Black & Decker", "BLACK+DECKER"], "magic_chef": ["Magic Chef"], "gl_inet": ["GL.iNet"]}
# Brand ids that are ordinary words: never gate on them (a 'home' or 'top' brand would match every notice).
BRAND_STOP = {"home", "top", "unique", "titan", "spt", "lago", "xo", "v7", "i-o", "tte", "elo", "core", "premium", "classic", "element", "the",
              "energystar"}
LEAD = re.compile(r"\bmodels?(?:\s+(?:numbers?|nos?\.?|#))?(?:\s+(?:include|includes|are|is))?(?:\s+(?:included|affected|recalled|involved)"
                  r"(?:\s+in\s+(?:this|the)\s+recall)?)?\s*[:#]?\s*", re.I)
PREFIX = re.compile(r"^\s*(?:must\s+)?(?:begin|beginning|begins|start|starting|starts|ending|ends|end)\s+with\b|^\s*series\b", re.I)
TOKEN = re.compile(r"(?:[A-Z0-9][A-Z0-9./-]*[A-Z0-9])(?![A-Za-z0-9*])")
SEP = re.compile(r"(?:\s*(?:,|;|&|\band\b|\bor\b)\s*)+|\s+")
COMMERCIAL = re.compile(r"\bcommercial\b", re.I)      # commercial / coin-op units are not the residential consumer categories: enrich only, never mint
NEG = re.compile(r"\bnot\b|\bno other\b|\bexcluded\b|\bexcept\b", re.I)


def today():
    return time.strftime("%Y-%m-%d", time.gmtime())


def year_pages():
    """{year: snapshot-log record} of the latest status-200 year page in the shared store."""
    st = C.BlobStore(SHARED)
    return {int(k[6:]): r for k, r in st.latest().items() if k.startswith("_year_")}


def pull(refresh=False, first=FIRST_YEAR):
    st, have = C.BlobStore(SHARED), year_pages()
    y1 = int(today()[:4])
    out = {}
    for y in range(first, y1 + 1):
        r = have.get(y)
        if r and not refresh and (y < y1 or r["fetched_at"][:10] == today()):
            out[y] = ("kept", r["fetched_at"]); continue
        url = API.format(y=y)
        snap, body = C.http_snapshot(st, Ref(SHARED, f"_year_{y}", url, {}), url, DELAY, ".json", ADAPTER)
        out[y] = (snap.status, len(json.loads(body)) if body else None)
        if body is None:
            print(f"pull: year {y} -> {snap.status}; stopping", file=sys.stderr)
            break
    return out


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def products(r):
    return r.get("Products") or []


def text_of(r):
    """Every free-text field that may print a model number: title, product names / models / descriptions, the notice description."""
    return "\n".join([clean(r.get("Title"))] + [clean(" ".join(filter(None, (p.get("Name"), p.get("Model"), p.get("Description"))))) for p in products(r)]
                     + [clean(r.get("Description"))])


def category_of(r):
    """First category in TYPES priority whose product-type pattern the title or a product name matches, else None."""
    hay = " | ".join([clean(r.get("Title"))] + [clean(p.get("Name")) for p in products(r)])
    return next((c for c, _ in TYPES if TYPE_RX[c].search(hay)), None)


def brand_rx(bid, name):
    alts = {bid.replace("_", " "), re.sub(r"\s*\(.*$", "", name or "").strip()} | set(BRAND_EXTRA.get(bid, []))
    alts = sorted({a for a in alts if len(a) >= 2}, key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(a).replace(r"\ ", r"[\s_-]?") for a in alts) + r")(?![A-Za-z0-9])", re.I)


def brands_named(r, brands):
    """-> (brands named in the product names, else the title, else the recalling firms), each a sorted list of brand ids."""
    firm = " | ".join(clean(x.get("Name")) for k in ("Manufacturers", "Importers", "Distributors") for x in (r.get(k) or []))
    for hay in (" | ".join(clean(p.get("Name")) for p in products(r)), clean(r.get("Title")), firm):
        hit = sorted(b for b, rx in brands.items() if rx.search(hay))
        if hit:
            return hit
    return []


def local_type(before):
    """Category of the LAST product-type phrase in the text just before a 'model' lead ('charging stands with model number MMA008 and power
    banks with model numbers BPB002'), or None."""
    best = None
    for c, rx in TYPE_RX.items():
        for m in rx.finditer(before):
            if best is None or m.end() > best[0]:
                best = (m.end(), c)
    return best[1] if best else None


def models_printed(text):
    """Model numbers the notice prints after a 'model(s) [number(s)]' lead, as written. A prefix list ('model numbers beginning with'),
    a 'model series', a wildcard (* or x placeholders) and any sentence with a negation (not / no other / excluded / except) yield
    nothing. Tokens need a letter AND a digit and 4-25 characters, upper case as printed (a lower-case word ends the list).
    -> [(model, category of the product-type phrase just before the lead or None)]."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])|\n", text):
        if NEG.search(sent):
            continue
        for m in LEAD.finditer(sent):
            rest, lt = sent[m.end():], local_type(sent[max(0, m.start() - 80):m.start()])
            if PREFIX.match(rest):
                continue
            pos = 0
            while True:
                tm = TOKEN.match(rest, pos)
                if not tm:
                    break
                tok = tm.group(0).rstrip(".")
                if not re.search(r"\d", tok):
                    break                     # an upper-case WORD (brand, 'USB-C') ends the list
                frag = re.match(r" ([A-Z0-9]{1,3})(?![A-Za-z0-9])", rest[tm.end():])
                if frag and re.search(r"\d", frag.group(1)):
                    break                     # 'SBS24 I0': a model split by a stray space is ambiguous; neither half is a model
                if 4 <= len(tok) <= 25 and re.search(r"[A-Z]", tok) and tok not in [o for o, _ in out]:
                    out.append((tok, lt))
                pos = tm.end()
                sm = SEP.match(rest, pos)
                if not sm or sm.end() == pos:
                    break
                pos = sm.end()
    return out


def first_date(s):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s or ""))
    return m.group(1) if m else None


def load_recalls():
    """-> ({recall number: recall}, {recall number: (year-page record)}) from the latest year pages of the shared store."""
    st, out, page = C.BlobStore(SHARED), {}, {}
    for y, rec in sorted(year_pages().items()):
        for r in json.loads(st.read_rec(rec)):
            n = str(r.get("RecallNumber") or r.get("RecallID"))
            out[n], page[n] = r, rec
    return out, page


def norm_model(v, brand):
    sys.path.insert(0, str(C.CODE / "scripts"))
    import identity as I          # the importer's own normalisation: an 'exact' match is exactly what import.py would merge
    return I.norm_value("mfr_model", v, brand)


def category_index(category):
    """From state/specsheet.sqlite (last import): {brand id: brand name} of model entities in this category, and {(brand, normalised
    model): value_raw} for model keys of entities some NON-cpsc source observed (a recall-only record minted by this overlay is not an
    'existing entity': it stays recall_only until a maker or certifier source lists the model)."""
    db = C.ROOT / "state" / "specsheet.sqlite"
    if not db.exists():
        return {}, {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    brands = {b: n for b, n in con.execute("SELECT DISTINCT brand, brand_name FROM entities WHERE category=? AND kind='model'", (category,))}
    have = {}
    for b, v, raw in con.execute(
            "SELECT e.brand, i.value, i.value_raw FROM identifiers i JOIN entities e ON e.id=i.entity_id WHERE e.category=? AND e.kind='model' "
            "AND i.scheme='mfr_model' AND i.role='key' AND EXISTS (SELECT 1 FROM attachments a WHERE a.entity_id=e.id AND a.source_id NOT LIKE 'cpsc-recalls%')",
            (category,)):
        have[(b, v)] = raw
    con.close()
    return brands, have


class _CpscRecalls:
    id, version = ID, VERSION
    category = None

    def __init__(self):
        self.store = C.BlobStore(self.source_id)

    def discover(self, checkpoint, net):
        got = pull()                     # past years reused, the current year re-pulled once a day (shared across category sources)
        bad = {y: s for y, (s, _) in got.items() if s not in ("kept", 200)}
        if bad:
            return Discovery([], False, f"year pages failed: {bad}", checkpoint or {})
        recalls, page = load_recalls()
        names, have = category_index(self.category)
        brx = {b: brand_rx(b, n) for b, n in names.items() if b not in BRAND_STOP and len(b) >= 2}
        by_brand = {}
        for (b, v), raw in have.items():
            by_brand.setdefault(b, []).append((v, raw))
        refs, st = {}, {"recalls": len(recalls), "of_type": 0, "brand_named": 0, "no_model_printed": 0, "multi_brand_not_minted": 0,
                        "existing": 0, "recall_only": 0, "brands_gated": len(brx)}

        def add(brand, model, n, kind):
            k = f"{brand}|{norm_model(model, brand)}"
            g = refs.setdefault(k, {"brand": brand, "model": model, "recalls": [], "match": kind, "pages": []})
            if kind == "existing":
                g["match"], g["model"] = "existing", model
            if n not in g["recalls"]:
                g["recalls"].append(n); g["pages"].append(page[n]["snapshot"])

        for n, r in sorted(recalls.items()):
            text = text_of(r)
            printed = [(m, lt) for m, lt in models_printed(text)]
            cat0 = category_of(r)
            mine = [m for m, lt in printed if (lt or cat0) == self.category]
            if cat0 != self.category and not mine:
                continue
            st["of_type"] += 1
            bs = brands_named(r, brx)
            if not bs:
                continue
            st["brand_named"] += 1
            hit = set()
            for m in mine:
                ex = [b for b in bs if (b, norm_model(m, b)) in have]
                for b in ex:
                    add(b, have[(b, norm_model(m, b))], n, "existing"); hit.add((b, norm_model(m, b)))
                if not ex and len(bs) == 1 and not COMMERCIAL.search(clean(r.get("Title"))):
                    add(bs[0], m, n, "recall_only")
                elif not ex:
                    st["multi_brand_not_minted"] += 1
            if cat0 == self.category:           # an existing model of a named brand printed anywhere in the notice (tables, lists)
                up = "\n".join(s for s in re.split(r"(?<=[.!?])\s+|\n", text) if not NEG.search(s)).upper()
                for b in bs:
                    for v, raw in by_brand.get(b, []):
                        if (b, v) not in hit and len(v) >= 4 and re.search(r"\d", v) and \
                                re.search(r"(?<![A-Z0-9])" + re.escape(raw.upper()) + r"(?![A-Z0-9])", up):
                            add(b, raw, n, "existing"); hit.add((b, v))
            if not mine and not hit:
                st["no_model_printed"] += 1
        for g in refs.values():
            st[g["match"]] += 1
        st["brands"] = sorted(brx)
        out = [Ref(self.source_id, k, page[g["recalls"][0]]["url"], g) for k, g in sorted(refs.items())]
        return Discovery(out, True, None, st)

    def fetch(self, ref, prior, net):
        """No network: the ref's recall objects are copied verbatim out of the stored year pages into one canonical JSON blob."""
        h = ref.hints or {}
        recalls, page = load_recalls()
        now = time.strftime("%FT%TZ", time.gmtime())
        rs = [recalls[n] for n in h.get("recalls") or [] if n in recalls]
        if not rs:
            s = C.Snapshot("sha256:", ref, "recall_not_in_pages", now, ref.url, {})
            self.store.append(s, ADAPTER, ".json")
            return s
        body = json.dumps({"brand": h["brand"], "model": h["model"], "match": h["match"], "category": self.category,
                           "recalls": sorted(rs, key=lambda r: str(r.get("RecallNumber")))}, sort_keys=True, ensure_ascii=False).encode()
        p0 = page[str(rs[-1].get("RecallNumber"))]
        s = C.Snapshot(self.store.put(body, ".json"), ref, 200, max(page[str(r.get("RecallNumber"))]["fetched_at"] for r in rs), p0["final_url"], {})
        self.store.append(s, ADAPTER, ".json")
        return s

    def parse(self, snap, blobs, profile):
        return parse_bundle(snap, json.loads(blobs.read(snap.snapshot, ".json")))


REMEDY = {"replace": "replace", "replacement": "replace", "refund": "refund", "repair": "repair", "new instructions": "new_instructions",
          "dispose": "dispose", "label": "label", "other": "other"}


def parse_bundle(snap, b):
    pr = ParseResult()
    rs = sorted(b.get("recalls") or [], key=lambda r: (first_date(r.get("RecallDate")) or "", str(r.get("RecallNumber"))))
    model, brand = b.get("model"), b.get("brand")
    pr.sources = [{"id": "s1", "url": snap.final_url or snap.ref.url, "label": "U.S. CPSC Recalls API (saferproducts.gov)", "source_id": snap.ref.source_id,
                   "tier": "regulatory", "retrieved_at": snap.fetched_at, "snapshot": snap.snapshot}]
    if not rs or not model or not brand:
        pr.absences.append({"key": "*", "reason": "no recall naming this model", "source": "s1"})
        return pr
    text = "\n".join(text_of(r) for r in rs).upper()
    if not re.search(r"(?<![A-Z0-9])" + re.escape(model.upper()) + r"(?![A-Z0-9])", text):     # re-checked on the stored notice text
        pr.absences.append({"key": "*", "reason": f"model {model!r} not printed in the stored notices", "source": "s1"})
        return pr
    pr.identifiers.append({"scheme": "mfr_model", "value": model, "value_raw": model, "issuer": brand, "market": None, "package_level": "model",
                           "role": "key", "sources": ["s1"]})
    for r in rs:
        pr.identifiers.append({"scheme": "x_cpsc_recall", "value": str(r.get("RecallNumber")), "value_raw": str(r.get("RecallNumber")),
                               "issuer": "cpsc", "role": "alias", "sources": ["s1"]})
    nm = next((clean(p.get("Name")) for r in reversed(rs) for p in products(r) if clean(p.get("Name"))), None)
    if nm:
        pr.aliases.append({"text": nm[:120], "kind": "certifier_listing", "source": "s1", "observed_at": snap.fetched_at})
    obs = snap.fetched_at
    ids = [str(r.get("RecallNumber")) for r in rs]
    loc = {"model_code": model, "cpsc_recall": ",".join(ids)}

    def emit(key, value, raw, quote=None):
        pr.claims.append(claim(model, key, value, None, raw, "s1", ADAPTER, STAGE, obs, dict(loc), quote))

    def hazard(r):
        hz = clean(next((h.get("Name") for h in r.get("Hazards") or [] if clean(h.get("Name"))), ""))
        return hz[:200] or "hazard not stated"

    summary = " | ".join(f"CPSC {r.get('RecallNumber')} ({first_date(r.get('RecallDate'))}): {hazard(r)}" for r in rs)
    last = rs[-1]
    emit("safety.recall", summary, summary, clean(last.get("Title")))
    emit("safety.recall_id", ids, "RecallNumber: " + ", ".join(ids))
    d = first_date(last.get("RecallDate"))
    if d:
        emit("safety.recall_date", d, f"RecallDate: {last.get('RecallDate')}")
    rem = sorted({REMEDY.get(clean(o.get("Option")).lower(), "other") for r in rs for o in r.get("RemedyOptions") or [] if clean(o.get("Option"))})
    if rem:
        emit("safety.recall_remedy", rem, "RemedyOptions: " + ", ".join(clean(o.get("Option")) for r in rs for o in r.get("RemedyOptions") or []))
    urls = [clean(r.get("URL")) for r in rs if clean(r.get("URL"))]
    if urls:
        emit("safety.recall_url", urls[-1], "URL: " + " ; ".join(urls))
    if b.get("match") == "recall_only":
        emit("gen.record_kind", "recall_only", "no maker or certifier record of this model in this category: recall facts only (coordinator ruling r12)")
    pr.fingerprints = {"raw": snap.snapshot, "model": model, "brand": brand, "recalls": ids, "match": b.get("match")}
    return pr


# One registry source per category (registry SOURCES maps a source to exactly one category).
# laptops / ssds / power-strips are not here: their importers are not 'model' (MTM / configuration keys), so an exact maker-model overlay has
# nothing to attach to. Run a category's discover AFTER its first import (brands + existing models are read from state/specsheet.sqlite).
CATEGORIES = ["air-purifiers", "chargers", "clothes-dryers", "clothes-washers", "dishwashers", "freezers", "monitors", "power-banks", "power-stations",
              "refrigerators", "robot-vacuums", "routers", "smart-home", "tvs"]
CLASSES = {}
for _c in CATEGORIES:
    CLASSES[_c] = type(f"CpscRecalls_{_c.replace('-', '_')}", (_CpscRecalls,), {"source_id": f"cpsc-recalls-{_c}", "categories": {_c}, "category": _c})
    globals()[CLASSES[_c].__name__] = CLASSES[_c]

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pull":
        for y, v in pull(refresh="--refresh" in sys.argv).items():
            print(y, *v)
        raise SystemExit(0)
    cat = sys.argv.pop(1) if len(sys.argv) > 1 and sys.argv[1] in CLASSES else None
    if cat is None:
        raise SystemExit(f"usage: cpsc_recalls.py pull [--refresh] | cpsc_recalls.py <{'|'.join(CLASSES)}> discover|fetch|parse|run")
    _run.main(CLASSES[cat]())
