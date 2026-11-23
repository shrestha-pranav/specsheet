"""Bundle packages (A3-impl r6): mint `package` entities from a corroborated bundle SKU with explicit member models. Used by import.py
(importer 'model') for categories whose research/<cat>/category.yaml lists `bundle_packages` in `features`.

Candidates (two shapes adapters already emit; no adapter change):
  fingerprints.packages  [{sku, title}]  bundle variants a station page lists (power stations: '+ 200W Solar', '2 x DELTA 3', Anker add-on options)
  option SKUs            an mfr_sku identifier whose option label names the page model plus an add-on or a pack word
                         (Narwal 'Freo S & Advanced Kit', Dreame 'X50 Ultra Complete / White'); `bundles.pack_words` in category.yaml
A title is split into members on '+', '＋' and ' & ' after promo prefixes ('(Members-only)'), a colour part ('Black / ', ' / White') and a BLUETTI
'| 1800W,...' tail are dropped. A member is `<n> x <name>`, `<name> x <n>`, `<n>*<name>` or `<name>`; 'Free <name>' stays a member.

Corroborated = ALL of:
  1. the page model is an explicit member: a segment equals the page model (key, name or marketing alias, generic words such as 'Portable Power
     Station' and a '(2048Wh)' capacity dropped), or '<model> <pack word>'; an add-on-only option title ('100W Bifacial Solar Panel', Anker) counts
     only when the SKU embeds the model key's digit run (B17631A9 contains 1763 of A1763);
  2. more than one item (members or quantity >= 2);
  3. every observation of that SKU (any page, any source of the brand) yields the same member set; a disagreement or an unparseable title for
     the same SKU = not minted, one identity_conflicts row per SKU;
  4. the SKU is not an identifier of a model / configuration / revision (a unit SKU sold with a free gift is not a bundle).
Other segments are linked to another model of the same brand when they name it exactly, else kept as a text component.
A minted package: key mfr_sku (level package), name = cleaned title, `contains` relation to each member model (method bundle:<source>, pinned to
the parser), `contents` [{entity|description, qty}] in extra. It has no claims, no parent and no family, so it inherits nothing (no physical or
shipping facts) and is never an index row; v1_publish lists it under its member models (`bundles`). An option SKU that is not minted stays a
configuration alias of the model, as before.
"""
import html, re

PROMO = re.compile(r"^\s*(?:[(（][^)）]{0,40}?(?:member|sale|credit|deal|limited|madness)[^)）]{0,40}[)）]\s*)+", re.I)
SEP = re.compile(r"\s*(?:\+|＋|\s&\s)\s*")
QTY_PRE = re.compile(r"^(\d{1,2})\s*[x×*]\s*(.+)$", re.I)
QTY_POST = re.compile(r"^(.+?)\s*(?<![A-Za-z])[x×*]\s*(\d{1,2})$", re.I)
COLOUR = re.compile(r"^[A-Za-z]{3,10}(?: [A-Za-z]{3,10})?$")
CAPACITY = re.compile(r"[(（]\s*\d[\d,.]*\s*k?wh\s*[)）]", re.I)    # '(2048Wh)': a capacity note, not a different unit
GENERIC = re.compile(r"(?i)\b(portable power station|power station|solar generator|robot vacuum(?: and mop| & mop)?|robot vacuum cleaner)\b")


def norm(s):
    s = CAPACITY.sub(" ", html.unescape(str(s or "")))
    return re.sub(r"[^a-z0-9]", "", GENERIC.sub(" ", s).lower())


def clean_title(title):
    t = re.sub(r"\s+", " ", html.unescape(str(title or ""))).strip()
    t = re.sub(r"\s+", " ", GENERIC.sub(" ", PROMO.sub("", t))).strip()      # 'Freo 20 Robot Vacuum & Mop' is one item, not two
    parts = [p.strip() for p in t.split(" / ")]
    if len(parts) == 2:
        col = [p for p in parts if COLOUR.fullmatch(p)]
        if len(col) == 1:
            parts = [p for p in parts if p is not col[0]]
    if len(parts) != 1:
        return None
    return parts[0].split("|")[0].strip() or None


def segments(title):
    """-> [(name, qty)] or None (unparseable)."""
    t = clean_title(title)
    if not t or t.lower() == "default title":
        return None
    out = []
    for s in SEP.split(t):
        s = s.strip(" ,")
        if not s or len(s) > 80:
            return None
        m = QTY_PRE.match(s)
        if m:
            out.append((m[2].strip(), int(m[1]))); continue
        m = QTY_POST.match(s)
        if m:
            out.append((m[1].strip(), int(m[2]))); continue
        out.append((s, 1))
    return out


FREE = re.compile(r"(?i)^free\b|^\(\s*free\b")
FREE_NOTE = re.compile(r"(?i)\s*[(（]\s*free\b[^)）]*[)）]")


def members(title, names, key, sku, pack_words=(), option_only_ok=False, brand_name=""):
    """names: normalised page-model names. -> ({"model": qty, "parts": [(text, qty)]}, None) or (None, reason). Free promotional items are not
    package contents (the same SKU is sold with and without them as campaigns change): they are dropped before the checks."""
    seg = segments(title)
    if seg is None:
        return None, "title has no explicit member list"
    bn = norm(brand_name)
    qty, parts = 0, []
    pw = [w.lower() for w in pack_words]
    for name, n in seg:
        name = FREE_NOTE.sub("", name).strip()
        if FREE.search(name):
            continue
        nn = norm(name)
        hit = nn in names or (bn and nn.startswith(bn) and nn[len(bn):] in names)
        if not hit:
            for w in pw:
                if name.lower().endswith(" " + w) and norm(name[: -len(w)]) in names:
                    hit = True; parts.append((f"'{name[-len(w):]}' pack contents (not itemised by the source)", 1)); break
        if hit:
            qty += n
        else:
            parts.append((name, n))
    named = qty > 0
    if qty == 0:
        digits = max(re.findall(r"\d{4,}", str(key)), key=len, default=None)
        if not (option_only_ok and " " not in str(key).strip() and len(seg) == 1 and digits and digits in str(sku).replace("-", "")):
            return None, "page model is not an explicit member"
        qty = 1
    if qty + sum(n for _, n in parts) < 2:
        return None, "a single item (not a bundle)"
    return {"model": qty, "parts": parts, "named": named}, None


def part_sig(text):
    """Member identity for corroboration: the printed designations (numbers + unit, model tokens), else the normalised text. '220W Solar Panel'
    and '220W Portable Solar Panel' agree; '160W' and '220W' do not."""
    toks = sorted(set(re.findall(r"[a-z]*\d+(?:\.\d+)?[a-z]*", html.unescape(str(text)).lower())))
    return " ".join(toks) if toks else norm(text)


def page_names(e, mi, pr, brand_name):
    out = {norm(mi["value"]), norm(mi.get("value_raw")), norm(e.name)}
    out |= {norm(a["text"]) for a in pr.get("aliases") or [] if a.get("kind") == "marketing_name"}
    bn = norm(brand_name)
    out |= {x[len(bn):] for x in list(out) if bn and x.startswith(bn)}
    out.discard("")
    return out


def collect(world, e, brand, mi, pr, sid, rec, ob, parser, cfg, brand_name):
    """Called by import.do_model for every model observation. Records candidates on world.bundle_cands; -> ids (python id()) of option-SKU
    identifiers that are bundle candidates (do_model does not alias them; mint() re-aliases the ones it does not mint)."""
    cands = world.__dict__.setdefault("bundle_cands", [])
    names = page_names(e, mi, pr, brand_name)
    pw = (cfg or {}).get("pack_words") or []
    skip = set()
    for p in ((pr.get("fingerprints") or {}).get("packages") or []):
        sku = str(p.get("sku") or "").strip()
        if len(sku) < 4:
            continue
        m, why = members(p.get("title"), names, mi["value"], sku, pw, option_only_ok=True, brand_name=brand_name)
        cands.append({"brand": brand, "sku": sku, "title": p.get("title"), "model": e, "m": m, "why": why, "sid": sid, "rec": rec, "pr": pr,
                      "ob": ob, "parser": parser, "ident": None})
    for i in pr["identifiers"]:
        if i is mi or i["scheme"] != "mfr_sku" or not i.get("option"):
            continue
        m, why = members(i["option"], names, mi["value"], i["value"], pw, option_only_ok=False, brand_name=brand_name)
        if m is None:
            continue           # a colour / plain option: an ordinary configuration alias
        cands.append({"brand": brand, "sku": str(i["value"]).strip(), "title": i["option"], "model": e, "m": m, "why": None, "sid": sid, "rec": rec,
                      "pr": pr, "ob": ob, "parser": parser, "ident": i})
        skip.add(id(i))
    return skip


def mint(world, stats, h):
    """After every source (and the deferred pages) of a category: corroborate and mint. h = import.py helpers (K, add_ident, add_src, link, parser
    slot, slug)."""
    import collections
    cands = world.__dict__.get("bundle_cands") or []
    taken = set()          # SKUs that name a model / configuration / revision (unit SKUs, aliases)
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
        groups[(c["brand"], re.sub(r"[^A-Z0-9]", "", c["sku"].upper()))].append(c)
    out = []
    for (brand, nsku), cs in sorted(groups.items(), key=lambda kv: kv[0]):
        ok = [c for c in cs if c["m"] is not None]
        if not ok:
            stats["bundle_not_explicit"] += 1
            continue
        sigs = {}
        for c in ok:
            mem = collections.Counter({c["model"]: c["m"]["model"]})
            parts = []
            for text, n in c["m"]["parts"]:
                hit = by_name.get((brand, norm(text))) or set()
                if len(hit) == 1:
                    mem[next(iter(hit))] += n
                else:
                    parts.append((text, n))
            c["mem"], c["parts"] = mem, parts
            sigs[c["sid"], c["rec"]["ref"], c["title"]] = (tuple(sorted((x.idhint or x.name or "", n) for x, n in mem.items())),
                                                           tuple(sorted((part_sig(t), n) for t, n in parts)))
        e0 = ok[0]["model"]
        why = None
        if len(set(sigs.values())) > 1:
            why = "one SKU, different member sets: " + " | ".join(sorted({c["title"] for c in ok}))[:220]
        elif len(ok) < len(cs):
            why = "one SKU, some titles do not list members: " + " | ".join(sorted({str(c["title"]) for c in cs if c["m"] is None}))[:220]
        elif (brand, nsku) in taken:
            why = "SKU is also a unit / configuration identifier"
        if why:
            stats["bundle_not_corroborated"] += 1
            if not why.startswith("SKU is also"):
                world.id_review.append((e0, "mfr_sku", ok[0]["sku"], f"bundle SKU not minted: {why}"))
            for c in cs:
                if c["ident"] is not None:
                    h["add_ident"](c["model"], c["ident"], role="alias")
            continue
        canon = sorted(ok, key=lambda c: (len(clean_title(c["title"]) or ""), str(c["title"]), c["sid"], str(c["rec"]["ref"])))[0]
        h["parser"]["current"] = canon["parser"]
        pk = world.get("package", brand, [h["K"]("mfr_sku", canon["sku"], brand, "package")], canon["ob"])
        if pk is None:
            stats["bundle_quarantined"] += 1
            continue
        pk.idhint = pk.idhint or f"{brand}-{h['slug'](canon['sku'])}"
        t = clean_title(canon["title"])
        pk.name = pk.name or (t if canon["m"]["named"] else f"{canon['model'].name} + {t}")
        h["add_ident"](pk, {"scheme": "mfr_sku", "value": canon["sku"], "value_raw": canon["sku"], "issuer": brand, "market": None}, role="key", level="package")
        for c in ok:
            h["add_src"](pk, c["pr"], c["rec"])
            pk.obs.add(c["ob"])
        for x in sorted(canon["mem"], key=lambda x: x.idhint or ""):
            h["link"](pk, "contains", x, f"bundle:{canon['sid']}")
        pk.__dict__["bundle_contents"] = [(x, None, n) for x, n in sorted(canon["mem"].items(), key=lambda kv: kv[0].idhint or "")] + \
                                         [(None, text, n) for text, n in canon["parts"]]
        pk.extra["bundle"] = {"sku_title": canon["title"], "observations": len(ok)}
        stats["bundle_packages"] += 1
        out.append(pk)
    return out


def finalize(world):
    """Once ids exist: contents [{entity|description, qty}] (record.schema.json $defs contents) into extra."""
    for e in world.ents:
        bc = e.__dict__.get("bundle_contents")
        if bc:
            e.extra["contents"] = [({"entity": x.id} if x is not None else {"description": t}) | {"qty": n} for x, t, n in bc]
