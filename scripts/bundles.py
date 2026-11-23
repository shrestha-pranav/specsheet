"""Bundle packages (A3-impl r6, r7 = transform bundles@2): mint `package` entities from a manufacturer bundle SKU with explicit member models.
Used by import.py (importer 'model') for categories whose research/<cat>/category.yaml lists `bundle_packages` in `features`.

Evidence level (stated, review 4): the manufacturer's own store lists the SKU with a title that itemises it. That listing IS the SKU-to-contents
statement; agreement among several listings is CONSISTENCY of collected observations, not independent corroboration (one listing can mint).
extra.bundle.evidence says which.

Candidates (two shapes adapters already emit; no adapter change):
  fingerprints.packages  [{sku, title}]  bundle variants a station page lists ('+ 200W Solar', '2 x DELTA 3')
  option SKUs            an mfr_sku identifier whose option label names the page model plus an add-on ('Freo S & Advanced Kit')

Parse (r7, conservative; unknown text is preserved, never dropped silently):
  - a leading campaign tag ('(Members-only)', '(Flash Sale)') is a campaign label, not content;
  - ' / ' splits off a colour ONLY when the part is in COLOURS (reviewed list); any other slash = unparseable;
  - a '|' tail is kept as `unparsed` and marks contents incomplete; a tail that itself looks like a member list (+, &, N x) = unparseable;
  - members split on '+', '＋', ' & '; quantities `<n> x name`, `name x <n>`, `<n>*name`; n must be 1..99 (0 = unparseable);
  - promotions: 'Free <name>', '<name> (Free)' (the whole item) and '<name> (Free <other>)' (the other item) are promotions, recorded separately
    with their observation date, never contents and never counted; any other 'free' wording = unparseable;
  - '<model> <pack word>' ('X50 Ultra Complete') names the model and marks contents incomplete; it fabricates no component and does not count
    towards the two-item threshold;
  - the page model must be NAMED by a segment (key, name or marketing alias, brand prefix allowed). A capacity note on that segment
    ('(2048Wh)') must equal a capacity the page itself states for the model, else the segment is another product ('Explorer 5000 Plus (10kWh)').
    There is NO inference from SKU digits (r6 let 'B17631A9' imply A1763 for an add-on-only title: removed).
Mint = ALL of:
  1. the page model is named; 2. more than one counted item; 3. every observation of the exact SKU (any page, any source of the brand) gives the
  same canonical MULTISET {member model: qty} + {canonical description: qty} (equivalent repeated parts are summed; descriptions are compared in
  full with only SYNONYMS folded: '200W rigid' != '200W flexible'); 4. one stated market for all observations (unstated is not US); 5. no other
  SKU of the brand differs from it only by punctuation; 6. the SKU is no plain option/unit/configuration identifier.
Failing 3-6 is a DISPUTE: nothing minted, the SKU is not re-attached anywhere, one identity_conflicts row (reviewable via the ledger). A plain
unit SKU (6, taken by a model/configuration) stays that entity's identifier. A minted package: key mfr_sku (level package, market of the
observations), `contains` -> each member model (method bundle:<source>, parser '<adapter parser>+bundles@2' so a relation policy pins this
transform and its fingerprint), contents [{entity|description, qty}], extra.bundle {evidence, complete, unparsed, promotions, market, period}.
It has no claims, parent or family (inherits nothing) and is never an index row.
"""
import collections, hashlib, html, re
from pathlib import Path

ID, VERSION = "bundles", 2
TRANSFORM = f"{ID}@{VERSION}"


def fingerprint():
    """Same shape as registry.parser_fingerprint: the audited transform is pinned in rel/bundle-contents@2 audit.parsers."""
    p = Path(__file__)
    return "sha256:" + hashlib.sha256(p.name.encode() + b"\0" + p.read_bytes() + b"\0").hexdigest()[:20]


PROMO = re.compile(r"^\s*((?:[(（][^)）]{0,40}?(?:member|sale|credit|deal|limited|madness)[^)）]{0,40}[)）]\s*)+)", re.I)
SEP = re.compile(r"\s*(?:\+|＋|\s&\s)\s*")
QTY_PRE = re.compile(r"^(\d{1,2})\s*[x×*]\s*(.+)$", re.I)
QTY_POST = re.compile(r"^(.+?)\s*(?<![A-Za-z])[x×*]\s*(\d{1,2})$", re.I)
COLOURS = {"black", "white", "grey", "gray", "silver", "blue", "green", "red", "dune white", "space grey", "space gray", "dark grey",
           "light grey", "matte black", "midnight black", "titanium", "graphite", "beige", "sand"}
CAPACITY = re.compile(r"[(（]\s*(\d[\d,.]*)\s*(k?wh)\s*[)）]", re.I)    # '(2048Wh)': must equal the page's own stated capacity
GENERIC = re.compile(r"(?i)\b(portable power station|power station|solar generator|robot vacuum(?: and mop| & mop)?|robot vacuum cleaner)\b")
FREE_LEAD = re.compile(r"(?i)^free\s+(.+)$")
FREE_NOTE = re.compile(r"(?i)\s*[(（]\s*free\b\s*([^)）]*?)\s*[)）]")
LISTLIKE = re.compile(r"\+|＋|\s&\s|(?<![A-Za-z])\d{1,2}\s*[x×*]\s|\s[x×*]\s*\d{1,2}\b", re.I)
SYNONYMS = [(re.compile(r"\bpanels\b"), "panel")]      # reviewed: plural only. Nothing else is folded (rigid != flexible, 'portable' kept)
CAP_KEYS = ("cap.energy_wh", "pwr.battery_wh")


def norm(s):
    s = CAPACITY.sub(" ", html.unescape(str(s or "")))
    return re.sub(r"[^a-z0-9]", "", GENERIC.sub(" ", s).lower())


def canon_desc(text):
    """Conservative full description for multiset agreement: case, whitespace and the '×' glyph only, plus SYNONYMS."""
    t = re.sub(r"\s+", " ", html.unescape(str(text)).replace("×", "x").lower()).strip(" ,.;")
    for rx, rep in SYNONYMS:
        t = rx.sub(rep, t)
    return t


def capacities_of(pr):
    """Wh capacities the page itself states for its model (claims), for checking a '(2048Wh)' note."""
    out = set()
    for c in pr.get("claims") or []:
        if c.get("key") in CAP_KEYS and c.get("status") == "known" and isinstance(c.get("value"), (int, float)):
            out.add(float(c["value"]) * (1000 if str(c.get("unit") or "").lower() == "kwh" else 1))
    return out


def _cap_ok(seg, caps):
    m = CAPACITY.search(seg)
    if not m:
        return True
    v = float(m[1].replace(",", "")) * (1000 if m[2].lower() == "kwh" else 1)
    return any(abs(v - c) <= max(1.0, 0.005 * c) for c in caps or ())


def parse_title(title):
    """-> ({"segments": [(text, qty)], "promotions": [text], "unparsed": [text], "campaign", "colour"}, None) or (None, reason)."""
    t = re.sub(r"\s+", " ", html.unescape(str(title or ""))).strip()
    if not t or t.lower() == "default title":
        return None, "title has no explicit member list"
    out = {"segments": [], "promotions": [], "unparsed": [], "campaign": None, "colour": None}
    m = PROMO.match(t)
    if m:
        out["campaign"] = m[1].strip(); t = t[m.end():].strip()
    t = re.sub(r"\s+", " ", GENERIC.sub(" ", t)).strip()      # 'Freo 20 Robot Vacuum & Mop' is one item, not two
    parts = [p.strip() for p in t.split(" / ")]
    if len(parts) == 2 and sum(p.lower() in COLOURS for p in parts) == 1:
        out["colour"] = next(p for p in parts if p.lower() in COLOURS)
        parts = [p for p in parts if p.lower() not in COLOURS]
    if len(parts) != 1 or "/ " in parts[0] or " /" in parts[0]:
        return None, "slash part is not a known colour (contents may be hidden in it)"
    head, _, tail = parts[0].partition("|")
    head, tail = head.strip(), tail.strip()
    if tail:
        if LISTLIKE.search(tail):
            return None, "pipe tail looks like a member list"
        out["unparsed"].append(tail)
    if not head:
        return None, "title has no explicit member list"
    for s in SEP.split(head):
        s = s.strip(" ,")
        if not s or len(s) > 80:
            return None, "empty or overlong member segment"
        fm = FREE_NOTE.search(s)
        if fm:
            s = FREE_NOTE.sub("", s).strip()
            if not fm[1]:                       # '<name> (Free)': the item itself is the promotion
                out["promotions"].append(s); continue
            out["promotions"].append(fm[1])     # '<name> (Free <other>)': the other item is
        fl = FREE_LEAD.match(s)
        if fl:
            out["promotions"].append(fl[1].strip()); continue
        if re.search(r"(?i)\bfree\b", s):
            return None, "unrecognised 'free' wording"
        q = QTY_PRE.match(s)
        if q:
            n, s = int(q[1]), q[2].strip()
        else:
            q = QTY_POST.match(s)
            n, s = (int(q[2]), q[1].strip()) if q else (1, s)
        if n <= 0:
            return None, "nonpositive quantity"
        out["segments"].append((s, n))
    return out, None


def members(title, names, pack_words=(), brand_name="", caps=None):
    """names: normalised page-model names. -> ({"model": qty, "parts": [(text, qty)], "complete", "promotions", "unparsed", "pack"}, None)
    or (None, reason)."""
    p, why = parse_title(title)
    if p is None:
        return None, why
    bn = norm(brand_name)
    pw = [w.lower() for w in pack_words]
    qty, parts, pack = 0, [], None

    def named(s):
        nn = norm(s)
        return _cap_ok(s, caps) and (nn in names or bool(bn and nn.startswith(bn) and nn[len(bn):] in names))

    for name, n in p["segments"]:
        if named(name):
            qty += n; continue
        w = next((w for w in pw if name.lower().endswith(" " + w) and named(name[: -len(w) - 1])), None)
        if w:
            qty += n; pack = name[-len(w):]; continue
        parts.append((name, n))
    if qty == 0:
        return None, "page model is not an explicit member"
    agg = collections.OrderedDict()
    for text, n in parts:                       # equivalent repeated parts are one multiset entry
        k = canon_desc(text)
        agg[k] = (agg[k][0], agg[k][1] + n) if k in agg else (text, n)
    parts = list(agg.values())
    if qty + sum(n for _, n in parts) < 2:
        return None, "a single item (not a bundle)" + (f"; '{pack}' pack contents are not itemised" if pack else "")
    return {"model": qty, "parts": parts, "named": True, "complete": not (pack or p["unparsed"]), "promotions": p["promotions"],
            "unparsed": p["unparsed"] + ([f"'{pack}' pack contents (not itemised by the source)"] if pack else []), "pack": pack}, None


def page_names(e, mi, pr, brand_name):
    out = {norm(mi["value"]), norm(mi.get("value_raw")), norm(e.name)}
    out |= {norm(a["text"]) for a in pr.get("aliases") or [] if a.get("kind") == "marketing_name"}
    bn = norm(brand_name)
    out |= {x[len(bn):] for x in list(out) if bn and x.startswith(bn)}
    out.discard("")
    return out


def sku_key(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def collect(world, e, brand, mi, pr, sid, rec, ob, parser, cfg, brand_name):
    """Called by import.do_model for every model observation. Records candidates on world.bundle_cands; -> ids (python id()) of option-SKU
    identifiers that are bundle candidates (do_model does not alias them; mint() re-aliases only plain unit SKUs)."""
    cands = world.__dict__.setdefault("bundle_cands", [])
    plain = world.__dict__.setdefault("bundle_plain_opts", set())
    caps = world.__dict__.setdefault("bundle_caps", {})
    names = page_names(e, mi, pr, brand_name)
    pw = (cfg or {}).get("pack_words") or []
    cp = capacities_of(pr)
    caps.setdefault(id(e), set()).update(cp)
    base = {"brand": brand, "model": e, "sid": sid, "rec": rec, "pr": pr, "ob": ob, "parser": parser, "market": mi.get("market"),
            "at": rec.get("fetched_at")}
    skip = set()
    for p in ((pr.get("fingerprints") or {}).get("packages") or []):
        sku = str(p.get("sku") or "").strip()
        if len(sku) < 4:
            continue
        m, why = members(p.get("title"), names, pw, brand_name, cp)
        cands.append(dict(base, sku=sku, title=p.get("title"), m=m, why=why, ident=None))
    for i in pr["identifiers"]:
        if i is mi or i["scheme"] != "mfr_sku" or not i.get("option"):
            continue
        m, why = members(i["option"], names, pw, brand_name, cp)
        if m is None:
            plain.add((brand, sku_key(i["value"])))      # a colour / plain option: an ordinary configuration alias
            continue
        cands.append(dict(base, sku=str(i["value"]).strip(), title=i["option"], m=m, why=None, ident=i))
        skip.add(id(i))
    return skip


def mint(world, stats, h):
    """After every source (and the deferred pages) of a category: check agreement and mint. h = import.py helpers (K, add_ident, add_src,
    link, parser slot, slug)."""
    cands = world.__dict__.get("bundle_cands") or []
    plain = world.__dict__.get("bundle_plain_opts") or set()
    caps = world.__dict__.get("bundle_caps") or {}
    taken = set()          # SKUs that name a model / configuration / revision (unit SKUs, aliases), punctuation-folded (collision = taken)
    by_name = collections.defaultdict(set)
    for x in world.ents:
        if x.kind == "package":
            continue
        for (sch, v), d in x.idents.items():
            if sch in ("mfr_sku", "mfr_model"):
                taken.add((x.brand, re.sub(r"[^A-Z0-9]", "", str(v).upper())))
        if x.kind == "model":
            for nm in {x.name} | {d["value"] for (sch, _), d in x.idents.items() if sch == "mfr_model" and d["role"] == "key"}:
                if norm(nm):
                    by_name[(x.brand, norm(nm))].add(x)
    groups = collections.defaultdict(list)
    for c in cands:
        groups[(c["brand"], sku_key(c["sku"]))].append(c)
    folded = collections.defaultdict(set)
    for brand, sk in groups:
        folded[(brand, re.sub(r"[^A-Z0-9]", "", sk))].add(sk)
    out = []
    for (brand, sk), cs in sorted(groups.items(), key=lambda kv: kv[0]):
        nsku = re.sub(r"[^A-Z0-9]", "", sk)
        ok = [c for c in cs if c["m"] is not None]
        if not ok:
            stats["bundle_not_explicit"] += 1
            continue
        sigs = {}
        for c in ok:
            mem = collections.Counter({c["model"]: c["m"]["model"]})
            parts = collections.OrderedDict()
            for text, n in c["m"]["parts"]:
                hit = {x for x in by_name.get((brand, norm(text))) or set() if _cap_ok(text, caps.get(id(x)))}
                if len(hit) == 1:
                    mem[next(iter(hit))] += n
                else:
                    k = canon_desc(text)
                    parts[k] = (parts[k][0], parts[k][1] + n) if k in parts else (text, n)
            c["mem"], c["parts"] = mem, list(parts.values())
            sigs[c["sid"], str(c["rec"]["ref"]), str(c["title"])] = (tuple(sorted((x.idhint or x.name or "", n) for x, n in mem.items())),
                                                                     tuple(sorted((k, n) for k, (_, n) in parts.items())))
        e0 = ok[0]["model"]
        markets = {c["market"] for c in cs}
        why, restore = None, False
        if len(folded[(brand, nsku)]) > 1:
            why = "SKU differs from another bundle SKU only by punctuation: " + ", ".join(sorted(folded[(brand, nsku)]))
        elif len(set(sigs.values())) > 1:
            why = "one SKU, different contents: " + " | ".join(sorted({str(c["title"]) for c in ok}))[:220]
        elif len(ok) < len(cs):
            why = "one SKU, some observations do not itemise it: " + " | ".join(sorted({str(c["title"]) for c in cs if c["m"] is None}))[:220]
        elif len(markets) > 1:
            why = "one SKU observed in different markets: " + ", ".join(sorted(m or "unstated" for m in markets))
        elif (brand, sk) in plain:
            why = "SKU is also listed as a plain (non-bundle) option"
        elif (brand, nsku) in taken:
            why, restore = "SKU is also a unit / configuration identifier", True
        if why:
            stats["bundle_unit_sku" if restore else "bundle_disputed"] += 1
            if restore:              # the model's own unit SKU (sold with an add-on option): it stays that model's identifier
                for c in cs:
                    if c["ident"] is not None:
                        h["add_ident"](c["model"], c["ident"], role="alias")
            else:                    # dispute: quarantined (identity_conflicts), not minted and not re-attached as an alias
                world.id_review.append((e0, "mfr_sku", ok[0]["sku"], f"bundle SKU not minted: {why}"))
            continue
        canon = sorted(ok, key=lambda c: (len(str(c["title"])), str(c["title"]), c["sid"], str(c["rec"]["ref"])))[0]
        h["parser"]["current"] = f"{canon['parser']}+{TRANSFORM}"
        pk = world.get("package", brand, [h["K"]("mfr_sku", canon["sku"], brand, "package")], canon["ob"])
        if pk is None:
            stats["bundle_quarantined"] += 1
            continue
        pk.idhint = pk.idhint or f"{brand}-{h['slug'](canon['sku'])}"
        head = parse_title(canon["title"])[0]
        pk.name = pk.name or " + ".join((f"{n} x {s}" if n > 1 else s) for s, n in head["segments"])
        market = next(iter(markets))
        h["add_ident"](pk, {"scheme": "mfr_sku", "value": canon["sku"], "value_raw": canon["sku"], "issuer": brand, "market": market},
                       role="key", level="package")
        for c in ok:
            h["add_src"](pk, c["pr"], c["rec"])
            pk.obs.add(c["ob"])
        for x in sorted(canon["mem"], key=lambda x: x.idhint or ""):
            h["link"](pk, "contains", x, f"bundle:{canon['sid']}")
        pk.__dict__["bundle_contents"] = [(x, None, n) for x, n in sorted(canon["mem"].items(), key=lambda kv: kv[0].idhint or "")] + \
                                         [(None, text, n) for text, n in canon["parts"]]
        promos = sorted({(p, c["at"] or "") for c in ok for p in c["m"]["promotions"]})
        ats = sorted(c["at"] for c in ok if c["at"])
        pk.extra["bundle"] = {
            "sku_title": canon["title"], "observations": len(ok), "transform": TRANSFORM,
            "evidence": "manufacturer_store_listing" if len(ok) == 1 else "consistent_manufacturer_store_listings",
            "complete": all(c["m"]["complete"] for c in ok), "unparsed": sorted({u for c in ok for u in c["m"]["unparsed"]}),
            "promotions": [{"text": p, "observed_at": a} for p, a in promos], "market": market,
            "observed_from": ats[0] if ats else None, "observed_to": ats[-1] if ats else None}
        stats["bundle_packages"] += 1
        out.append(pk)
    return out


def finalize(world):
    """Once ids exist: contents [{entity|description, qty}] (record.schema.json $defs contents) into extra."""
    for e in world.ents:
        bc = e.__dict__.get("bundle_contents")
        if bc:
            e.extra["contents"] = [({"entity": x.id} if x is not None else {"description": t}) | {"qty": n} for x, t, n in bc]
