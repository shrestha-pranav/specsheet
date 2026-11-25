"""Shared pure parsers for the charger adapters (anker_chargers, belkin_chargers, shopify_chargers). No network.

Reuses the power-bank port model (_powerbank: PDO literals, PPS ranges, port segmentation, all-port totals with explicit membership) so a charger's
out.ports rows have exactly the power-bank shape {name, type, direction, max_w, fixed_pdos, pps}. _powerbank itself is NOT edited (its audited
fingerprints stay put); charger-only semantics live here.

Review-3 rules applied from the start (team/reviews/2026-11-23-astra-review-3.md):
- out.max_total_w = the maker's LABELLED total row only ('Total Output: 100W', a nameless 'xxW Max' line inside a Total Output row). Never the title,
  never a sum, never the largest port. out.all_ports_w = every port loaded at once, only from a printed combination whose members name every
  individual port (_powerbank.all_port_total) or an 'N Ports in Use' row with N = the printed port count. Belkin-style 'Wattage' rows (total or
  single-port not stated) go to out.rated_w and never feed either.
- Flags are affirmative only: pd.pps / pd.epr / gen.gan / phys.foldable_plug are emitted True on explicit evidence and never False.
- Numbers keep their literal (raw) and the row label (locator); unparseable labelled rows become status-unknown claims (preview evidence).
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _contract as C  # noqa: E402
import _powerbank as P  # noqa: E402

clean = P.clean
NUM = P.NUM


def lines_of(s):
    """HTML fragment -> text lines (br/li/p/div/tr boundaries)."""
    s = re.sub(r"<sup[^>]*>.*?</sup>", "", s or "", flags=re.S)
    s = re.sub(r"</(li|p|div|tr|h\d|dd|dt)>|<br\s*/?>|<li[^>]*>|\n", "\n", s)
    out = []
    for ln in s.split("\n"):
        t = clean(ln)
        if t:
            out.append(t)
    return out


def source(snap, title):
    return {"id": "s1", "url": snap.ref.url, "snapshot": snap.snapshot, "tier": "manufacturer", "title": title}


def ident(scheme, value, level, issuer, role="key", market="US", **extra):
    d = {"scheme": scheme, "value": value, "value_raw": value, "issuer": issuer, "market": market, "package_level": level, "role": role, "sources": ["s1"]}
    d.update({k: v for k, v in extra.items() if v is not None})
    return d


KIND_NOT = re.compile(r"wireless|magsafe|magnetic|\bqi2?\b|power ?bank|battery pack|\bhub\b|docking station|charg(?:er|ing) cable|^\W*(?:usb[- ]?c )?cable\b|\bstand\b|"
                      r"\b\d\s*-?\s*pack\b|\bbundle\b|power strip|surge|outlet extender|\b[23]-in-1\b", re.I)    # 2/3-in-1 = wireless phone+watch+earbuds sets


def charger_kind(text):
    """-> wall | desktop | car | travel | None (not a single charger model page). From the maker's own title/slug; used to pick the page,
    and as gen.form_factor (title-derived: preview only, never in a policy)."""
    t = text or ""
    if KIND_NOT.search(t) or not re.search(r"charger|charging station|power adapter|wall adapter|travel adapter", t, re.I):
        return None
    if re.search(r"\bcar\b|cigarette|vehicle", t, re.I):
        return "car"
    if re.search(r"desktop|charging station|\bstation\b|\bdesk\b", t, re.I):
        return "desktop"
    if re.search(r"travel|international|universal|us/uk/eu|worldwide", t, re.I):
        return "travel"
    return "wall"


def identity(pr, brand, model, title, skus, gtins, basis, extra_names=()):
    pr.identifiers.append(ident("mfr_model", model, "model", brand, basis=basis))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    for n in extra_names:
        if n and n != title:
            pr.aliases.append({"text": n, "kind": "marketing_name"})
    seen = {model.upper()}
    for s, name in skus:
        if s and s.upper() not in seen:
            seen.add(s.upper())
            pr.identifiers.append(ident("mfr_sku", s.upper(), "configuration", brand, role="alias", variant=name))
    for g in dict.fromkeys(gtins):
        pr.identifiers.append(ident("gtin", g, "package", "GS1", role="alias"))


def emit(pr, adapter, snap, model, key, value, raw, label, conditions=None, quote=None):
    P.emit(pr, adapter, snap, key, value, raw, label, model, conditions, quote)


# ---------------------------------------------------------------- generic labelled rows from a store page (tables, dt/dd, theme label/value pairs)
def _cells(tr):
    return [m[1] for m in re.finditer(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]


PAIR_PATTERNS = [
    re.compile(r'class="[^"]*(?:spec|attr|param|detail)[^"]*(?:label|title|name|key|heading)[^"]*"[^>]*>(.*?)</(?:span|div|p|h\d|dt|th|td|strong|b)>\s*'
               r'(?:</?(?:span|div|p|strong|b)[^>]*>\s*)*<(?:span|div|p|dd|td|ul)[^>]*class="[^"]*(?:value|content|desc|text|info|list)[^"]*"[^>]*>(.*?)</(?:span|div|p|dd|td|ul)>', re.S | re.I),
    re.compile(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", re.S | re.I),
    re.compile(r"<h6[^>]*>(.*?)</h6>\s*<p[^>]*>(.*?)</p>", re.S | re.I),
]

LABEL = re.compile(r"(?i)^(?:product model|model(?: number)?|item model number|input(?: voltage)?|ac input|rated input|dc input|output(?:s| power)?|"
                   r"total output(?: power)?|max(?:imum)? output|total power|power output|rated (?:output|power)|wattage|"
                   r"(?:single|dual|multi|1|2|3|4|one|two|three|four)[- ]ports?(?: output| in use)?|\d ports? in use|"
                   r"usb[- ]?[ac]\s*\d?(?:\s*/\s*(?:usb[- ]?)?[ac]?\d)*(?:\s*\+\s*(?:usb[- ]?)?[ac]\d?)*(?: output| port)?|type[- ]?c\s*\d?(?: output)?|"
                   r"c\d(?:\s*[/+]\s*c?\d)*(?:\s*\+\s*a\d?)*|a\d|ports?|number of ports|total (?:usb )?ports|number of usb-[ac] ports|"
                   r"(?:charging |supported |charge )?protocols?|charge agreement|technology|dimensions?|size|product dimensions|weight|"
                   r"net weight|item weight|plug(?: type)?|color|colour)$")


def page_rows(h, body_html=""):
    """-> [(label, [lines])] in page order, de-duplicated on (label, value). Sources: 2-cell table rows, label/value pairs, and 'Label: value'
    lines whose label is on the charger LABEL allowlist (the store page and the product's own body_html). Prose is never a row."""
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", h or "", flags=re.S)
    rows, seen = [], set()

    def put(lab, ls):
        lab = clean(lab).rstrip(":：").strip()
        ls = [x for x in ls if x]
        if not lab or not ls or len(lab) > 60:
            return
        sig = (lab.lower(), " | ".join(ls).lower())
        if sig not in seen:
            seen.add(sig)
            rows.append((lab, ls))

    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S | re.I):
        c = _cells(tr)
        if len(c) == 2:
            put(c[0], lines_of(c[1]))
    for rx in PAIR_PATTERNS:
        for a, b in rx.findall(h):
            put(a, lines_of(b))
    for src in (h, body_html or ""):
        for ln in lines_of(src):
            m = re.match(r"^([A-Za-z][A-Za-z0-9 /&()+.-]{0,40}?)\s*[:：]\s*(.{1,400})$", ln)
            if m and LABEL.match(m[1].strip()):
                put(m[1], [m[2]])
    return rows


# ---------------------------------------------------------------- row semantics
def _w(text):
    m = re.search(r"(?<![\d.])" + NUM + r"\s*W\b(?!h)", text or "")
    return P.fnum(m[1]) if m else None


def _ws(text):
    return [P.fnum(x) for x in re.findall(r"(?<![\d.])" + NUM + r"\s*W\b(?!h)", P.RANGE.sub(" ", clean(text or "")))]


PNAME = r"(?:USB[- ]?[AC]|Type[- ]?C|C|A)\s*\d?(?:\s*/\s*(?:USB[- ]?|Type-?)?[AC]?\s*\d)*"
PORT_PREFIX = re.compile(r"^\[?\s*(" + PNAME + r")\s*\]?\s*(?:[:：]|-(?=\s*\d)|–|—|\s(?=\d+(?:\.\d+)?\s*V))\s*(.+)$", re.I)
COMBO_LINE = re.compile(r"^(" + PNAME + r"(?:\s*(?:\+|&)\s*" + PNAME + r")+)\s*(?:[:：]|\s-\s|-(?=\s*\d)|–|\s(?=\()|\s(?=\d+(?:\.\d+)?\s*W))\s*(.+)$", re.I)
PAREN_PORTS = re.compile(r"(" + PNAME + r")\s*\(([^)]*?\d\s*W[^)]*)\)", re.I)
WORDN = {"one": 1, "single": 1, "two": 2, "dual": 2, "three": 3, "triple": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
INUSE = re.compile(r"^(\d|one|two|three|four|five|six|seven|eight)\s*-?\s*ports?\s*in\s*use(?:\s*output)?\s*(?:[:：-]\s*)?(.*)$", re.I)
COMBO_LABEL = re.compile(r"(?i)\b(?:dual|two|triple|three|four|five|six|multi|multiple|[2-9])[- ]?ports?\b(?! in use)|simultaneous|combination|multi-?port")
PORT_LABEL = re.compile(r"(?i)^(?:usb[- ]?[ac]\s*\d?|type[- ]?c\s*\d?|c\d|a\d|out\s*\d)(?:\s*/\s*(?:usb[- ]?)?[ac]?\d)*(?:\s*(?:output|port))?$")
OUT_LABEL = re.compile(r"(?i)^(?:(?:usb[- ]?[ac]\s*\d?|type[- ]?c\s*\d?|dc|single[- ]port|one[- ]port|\d[- ]port|dual[- ]port|two[- ]port|triple[- ]port|three[- ]port|"
                       r"four[- ]port|multi(?:ple)?[- ]port|total)\s*)?outputs?(?: power| interface)?(?:\s+\w+[- ]port)?$|^(?:single|dual|triple|multi)[- ]port$|"
                       r"^(?:\d|one|two|three|four|five|six|seven|eight)\s*ports?\s*in\s*use(?:\s*output)?$")


PROTO = re.compile(r"(?i)\bQC\s*\d|\bSCP\b|\bFCP\b|\bAFC\b|BC\s*1\.2|\bUFCS\b|\bPD\s*[23]\.\d")


def title_check(title, w):
    """The maker's title prints exactly one wattage and it differs from a labelled single-wattage row -> Unresolved (the page contradicts
    itself: Belkin BBC032 '65W Compact' with 'Wattage 20W'). The title is a consistency check only, never a value."""
    tw = set(_ws(re.sub(r"(?i)\(\s*\d+\s*W\s*max\s*\)", "", title)))
    if w is not None and len(tw) == 1 and w not in tw:
        return P.Unresolved(f"page row says {w} W, the maker's title says {next(iter(tw))} W")
    return w


def norm_pdo(t):
    """'5.0V==3.0A' -> '5.0V⎓3.0A'; '5V/9V/12V/15V⎓3A' -> '5V⎓3A / 9V⎓3A / 12V⎓3A / 15V⎓3A' (one shared current printed once)."""
    t = re.sub(r"(\d)\s*V\s*={1,2}\s*(\d)", r"\1V⎓\2", t or "")
    t = re.sub(r"(\d)\s*V\s*m\s*⎓", r"\1V⎓", t)
    t = re.sub(r"(\d)\s*V\s*~\s*(\d+(?:\.\d+)?\s*A\b)", r"\1V⎓\2", t)                 # UGREEN '5.0V~ 3.0A'
                                  # Anker '4.5V-21Vm⎓2.25A' typo
    t = re.sub(r"(\d(?:\.\d+)?)\s*V\s*[-–~]\s*(\d+(?:\.\d+)?\s*V)", r"\1-\2", t)     # '5V-11V⎓5A' -> '5-11V⎓5A' (a range, read by RANGE)

    def ex(m):
        vs = re.findall(r"(\d+(?:\.\d+)?)\s*V", m[1])
        return " / ".join(f"{v}V⎓{m[2]}A" for v in vs)
    return re.sub(r"((?:\d+(?:\.\d+)?\s*V\s*/\s*)+\d+(?:\.\d+)?\s*V)\s*⎓\s*(\d+(?:\.\d+)?)\s*A", ex, t)


def has_pdo(t):
    return bool(P.FIXED.search(t) or P.RANGE.search(t))


def _count_ports(text):
    """'2x USB-C & 1x USB-A' / '2 USB-C + 1 USB-A' / 'USB-C x2' -> (c, a) or (None, None)."""
    t = clean(text)
    c = a = 0
    hit = False
    for n, typ in re.findall(r"(\d)\s*[x×*]?\s*(?:USB[- ]?|Type-?)([AC])\b", t, re.I):
        hit = True; c += int(n) if typ.upper() == "C" else 0; a += int(n) if typ.upper() == "A" else 0
    if not hit:
        for typ, n in re.findall(r"(?:USB[- ]?|Type-?)([AC])\s*(?:ports?)?\s*[x×*]\s*(\d)\b", t, re.I):
            hit = True; c += int(n) if typ.upper() == "C" else 0; a += int(n) if typ.upper() == "A" else 0
    return (c, a) if hit else (None, None)


def port_name(name):
    """Spelling variants of one port name -> one form: 'USB-C 1 / C 2' and 'USB-C1/C2' -> 'USB-C1/C2' (space before a digit and around '/' dropped)."""
    return re.sub(r"\s*/\s*", "/", re.sub(r"(?<=[A-Za-z])\s+(?=\d)", "", name or ""))


class _Out:
    """Collects one page's output evidence: individual port rows, printed combinations, labelled totals, 'N ports in use' rows."""
    def __init__(self):
        self.ports, self.combos, self.totals, self.in_use, self.lit, self.unnamed_w = {}, [], [], [], [], []
        self.last = None

    def port(self, name, text):
        name = port_name(re.sub(r"(?i)\s*(?:output|port)$", "", clean(name)).strip()) or "Output"
        if name in self.ports and text in self.ports[name].split(" / "):      # a variant spelling repeating the same row (A2669 'USB-C 1 / C 2' + 'USB-C1/C2')
            self.last = name; return
        self.ports[name] = (self.ports.get(name, "") + " / " + text).strip(" /")
        self.last = name

    def line(self, ctx, ln, combo_ctx):
        ln = norm_pdo(clean(ln))
        if not ln:
            return
        self.lit.append(f"{ctx}: {ln}" if ctx else ln)
        if (m := INUSE.match(ctx or "")) or (m := INUSE.match(ln)):
            n = int(m[1]) if m[1].isdigit() else WORDN[m[1].lower()]
            rest = m[2] if INUSE.match(ln) else ln
            ws = _ws(rest.split("/ Total")[0])
            if ws and not has_pdo(rest):
                self.in_use.append((n, ws, f"{n} port(s) in use: {rest}"))
            if (t := re.search(r"(?i)total output\s*[:：]?\s*(?:up to\s*)?" + NUM + r"\s*W", rest)):
                self.totals.append((P.fnum(t[1]), rest))
            if has_pdo(rest) or PORT_PREFIX.match(rest):
                self.line("", rest, combo_ctx)
            return
        if re.match(r"(?i)^total\b", ln) or re.match(r"(?i)^total\b", ctx or ""):
            ws = _ws(ln)
            if ws:
                self.totals.append((ws[0], f"{ctx}: {ln}" if ctx else ln))
            return
        if (m := COMBO_LINE.match(ln)):
            self.combos.append((m[1], m[2])); return
        if (m := re.match(r"(?i)^PPS\s*(\d+(?:\.\d+)?)$", ctx or "")) and re.match(r"^\d", ln) and self.last:   # Anker A2147 'PPS 3.3' | '11V⎓3A'
            self.ports[self.last] += f" / PPS {m[1]}-{ln}"; return
        if re.match(r"(?i)^PPS\b", ctx or "") and self.last and has_pdo(ln):      # a 'PPS' sub-row belongs to the port printed just before it
            self.ports[self.last] += " / PPS " + ln; return
        if combo_ctx:
            pp = PAREN_PORTS.findall(ln)
            if len(pp) >= 2:
                self.combos.append((" + ".join(n for n, _ in pp), " + ".join(w for _, w in pp)))
            return
        if PROTO.search(ln) and "⎓" not in ln and not re.search(r"\d\s*W\b", ln):
            return                       # a per-port protocol list ('USB-C2: QC3.0 / PD3.0 / Apple 5V/2.4A'), not a PDO table
        if (m := PORT_PREFIX.match(ln)):
            self.port(m[1], m[2]); return
        pp = PAREN_PORTS.findall(ln)
        if len(pp) >= 2 and not has_pdo(ln):
            for n, w in pp:
                self.port(n, w)
            return
        if ctx and PORT_LABEL.match(ctx):
            if PROTO.search(ln) and "⎓" not in ln and not re.search(r"\d\s*W\b", ln):
                return
            self.port(ctx, ln); return
        if has_pdo(ln):
            if self.last and not re.search(r"(?i)\d+(?:\.\d+)?\s*W\s*max", self.ports[self.last]) and re.match(r"^\s*(?:PPS\b|\d+(?:\.\d+)?\s*-)", ln):
                self.ports[self.last] += " / " + ln            # continuation line of the previous port (PPS ranges on their own line)
            else:
                self.port("Output", ln)
            return
        if _ws(ln):
            self.unnamed_w.append(ln)

    def build(self):
        out = []
        for name, text in self.ports.items():
            fx, pps, mw, _ = P.pdos(text)
            out.append({"name": name, "type": P.port_type(name) if name != "Output" else None, "direction": "out", "max_w": mw,
                        "fixed_pdos": fx or None, "pps": pps or None})
        return out


def read_rows(pr, adapter, snap, model, title, kind, rows, colors=(), table="spec table", line=None):
    """rows = [(label, [(name, value)] | [value lines])] -> claims. One place for every charger store, so the semantics cannot drift per brand."""
    def add(k, v, raw, lab, cond=None, quote=None):
        emit(pr, adapter, snap, model, k, v, raw, lab, cond, quote)

    norm = []
    for lab, items in rows:
        its = [(x if isinstance(x, tuple) else ("", x)) for x in items]
        norm.append((clean(lab).rstrip(":").strip(), [(clean(n), norm_pdo(clean(v))) for n, v in its if clean(v) or clean(n)]))
    add("gen.product_line", line, title, "title")
    add("gen.form_factor", kind, title, "title / page kind (derived)")
    add("gen.color", list(dict.fromkeys(colors)), " | ".join(dict.fromkeys(colors)), "variant option Color")
    if re.search(r"\bGaN", title):
        add("gen.gan", True, title, "title (maker's product name)")
    o, unmapped, labels, done = _Out(), {}, [], set()
    c_cnt = a_cnt = None

    def once(k):
        if k in done:
            return False
        done.add(k)
        return True
    for lab, items in norm:
        ll = lab.lower()
        raw = " | ".join(f"{n}: {v}" if n else v for n, v in items)
        labels.append(lab)
        if re.match(r"(?:product )?model(?: number)?$|item model number$", ll):
            mv = items[0][1] if items else ""
            if mv and mv.upper() != model.upper() and len(mv) <= 30:
                pr.aliases.append({"text": mv, "kind": "label_model"})
        elif re.match(r"(?:ac |rated |dc )?input(?: voltage)?$", ll) and once("in"):
            vr = re.search(NUM + r"\s*V?\s*(?:-|–|~|to)\s*" + NUM + r"\s*V", raw)
            if vr or re.search(r"Hz|\d\s*A\b", raw):
                add("in.rating", raw[:120], raw, lab)
            if vr:
                add("in.voltage_range", f"{P.fnum(vr[1])}-{P.fnum(vr[2])} V", raw, lab)
            if re.search(r"DC\s*(?:12|24)|(?:12|24)\s*V\s*DC|\b12\s*V?\s*(?:-|/|–|~)\s*24\s*V", raw):
                add("in.type", "dc_vehicle", raw, lab)
            elif re.search(r"~|\bAC\b|Hz", raw):
                add("in.type", "ac_mains", raw, lab)
        elif re.match(r"total (?:output|capacity|wattage|power)(?: power)?$|max(?:imum)? total output$", ll):
            ws = [w for _, v in items for w in _ws(v)]
            if ws and (len(set(ws)) == 1 or not any(n for n, _ in items)):
                if not any(n for n, _ in items):
                    o.totals.append((ws[0], f"{lab}: {raw}"))
            for n, v in items:
                if n:
                    o.line(n, v, bool(COMBO_LABEL.search(n)))
        elif OUT_LABEL.match(lab) or PORT_LABEL.match(lab) or COMBO_LABEL.search(lab) or INUSE.match(lab) or re.match(r"(?i)^single[- ]port output", lab):
            combo = bool(COMBO_LABEL.search(lab)) and not INUSE.match(lab)
            ctx = lab if (PORT_LABEL.match(lab) or INUSE.match(lab) or re.match(r"(?i)^(?:usb[- ]?[ac]|type-?c)\s*\d?\s*output", lab)) else ""
            if ll in ("output", "outputs", "output power") and len(items) == 1 and not items[0][0] and not has_pdo(items[0][1]) and _ws(items[0][1]):
                add("out.rated_w", title_check(title, _ws(items[0][1])[0]), raw, lab, quote="maker's single Output wattage: total vs single-port not stated")
                continue
            for n, v in items:
                o.line(n or ctx, v, combo and not n)
        elif re.match(r"(?:total (?:usb )?ports|ports?|number of ports|total number of ports|charging ports?|port type)$", ll):
            if any(n for n, _ in items):          # Anker valueList [('USB-C','2'),('USB-A','1')]
                c_cnt = sum(int(v) for n, v in items if re.search(r"(?i)usb-?c|type-?c", n) and v.isdigit())
                a_cnt = sum(int(v) for n, v in items if re.search(r"(?i)usb-?a", n) and v.isdigit())
            else:
                c, a = _count_ports(raw)
                if c is not None:
                    c_cnt, a_cnt = c, a
                elif re.fullmatch(r"\d{1,2}", raw.strip()):
                    add("out.port_count", int(raw.strip()), raw, lab)
        elif ll in ("number of usb-c ports", "number of usb-a ports"):
            n_ = re.match(r"\d+", raw)
            if n_:
                if "usb-c" in ll:
                    c_cnt = int(n_[0])
                else:
                    a_cnt = int(n_[0])
        elif re.match(r"(?:charging |supported |charge |fast charging )?protocols?$|charge agreement$", ll):
            toks = sorted({x.strip(" .") for x in re.split(r"[/,、;|]|\band\b", re.sub(r"(?i)usb-?[ac]\d?\s*(?:port)?\s*[:：]|\([^)]*\)", " ", raw)) if 1 < len(x.strip(" .")) < 24})
            add("pd.protocols", toks, raw, lab)
            if re.search(r"\bPPS\b", raw):
                add("pd.pps", True, raw, lab, quote="the maker's protocol row names PPS")
        elif re.match(r"(?:usb-?c|type-?c)\s*\d?\s+(?:charging |supported |fast charging )?protocols?$", ll):     # r7: per-port 'USB-C1 Protocols' (UGREEN 500W)
            if re.search(r"\bPPS\b", raw):
                add("pd.pps", True, raw, lab, quote="the maker's USB-C port protocol row names PPS")
            else:
                unmapped[lab] = raw[:100]
        elif ll in ("wattage", "power output", "rated output", "rated power", "max power", "power"):
            add("out.rated_w", title_check(title, _w(raw)), raw, lab, quote="maker's single wattage row: total vs single-port not stated")
        elif ll == "technology":
            if re.search(r"\bGaN\b", raw):
                add("gen.gan", True, raw, lab)
        elif (ll.startswith("dimension") or ll in ("size", "product dimensions", "product size")) and dims(raw) and once("dims"):
            add("phys.dimensions", dims(raw), raw, lab)
            if ll == "product size" and grams(raw) and once("wt"):
                add("phys.weight", grams(raw), raw, lab)
        elif ll in ("weight", "net weight", "item weight", "product weight") and grams(raw) and once("wt"):
            add("phys.weight", grams(raw), raw, lab)
        elif ll.startswith("plug"):
            if re.search(r"foldable|folding", raw, re.I):
                add("phys.foldable_plug", True, raw, lab)
        else:
            unmapped[lab] = raw[:100]
    if c_cnt is not None or a_cnt is not None:
        lit = f"USB-C {c_cnt or 0}, USB-A {a_cnt or 0}"
        add("out.usb_c_count", c_cnt or 0, lit, "ports row")
        add("out.usb_a_count", a_cnt or 0, lit, "ports row")
        add("out.port_count", (c_cnt or 0) + (a_cnt or 0), lit, "ports row")
    ports = [p for p in o.build() if p["fixed_pdos"] or p["pps"] or p["max_w"]]
    lit = "; ".join(o.lit)[:1200]
    if ports:
        add("out.ports", ports, lit, "output rows")
        single = [p["max_w"] for p in ports if p.get("max_w")]
        add("out.max_single_port_w", max(single) if single else None, lit, "output rows", quote="best single port: largest printed per-port maximum")
        pps = [r for p in ports if p.get("pps") for r in p["pps"].split("; ")]
        named = [x for x in o.lit if re.search(r"(?i)^(?:USB-?C|Type-?C|C)\s*\d?\b[^;]*\bPPS\b", x)]     # r7: 'USB-C1: 100W Max – PD 3.0 and PPS' (HyperJuice)
        if not pps and named:
            add("pd.pps", True, "; ".join(named)[:600], "output rows", quote="a USB-C output row names PPS (no range printed)")
        if pps:
            add("pd.pps", True, lit, "output rows", quote="a PPS/variable range is printed for a port")
            rr = [m for m in (re.match(NUM + r"-" + NUM + r"V " + NUM + r"A", r) for r in pps) if m]
            if rr:
                add("pd.pps_max_current_a", max(P.fnum(m[3]) for m in rr), "; ".join(pps), "output rows (printed PPS ranges)")
                add("pd.pps_max_voltage", max(P.fnum(m[2]) for m in rr), "; ".join(pps), "output rows (printed PPS ranges)")
        vmax = [v for v in (P.pdos(p.get("fixed_pdos") or "")[3] for p in ports) if v]
        if vmax:
            add("pd.max_fixed_voltage", max(vmax), lit, "output rows (printed fixed PDOs)")
            if max(vmax) >= 28:
                add("pd.epr", True, lit, "output rows", quote="a fixed PDO of 28 V or more is printed (USB PD EPR)")
    if o.combos:
        add("out.simultaneous", "; ".join(f"{n}: {v}" for n, v in o.combos)[:400], lit, "output rows (printed combinations)")
    tw = sorted({t[0] for t in o.totals})
    if len(tw) == 1:
        add("out.max_total_w", title_check(title, tw[0]), o.totals[0][1], "labelled total", quote="maker's labelled total-output row")
    elif len(tw) > 1:
        add("out.max_total_w", P.Unresolved("labelled total rows disagree: " + ", ".join(f"{x} W" for x in tw)), " | ".join(t[1] for t in o.totals), "total rows")
    # all ports at once: explicit membership only (review 3)
    inv = {t for p in ports for t in P.port_tokens(p["name"])} if ports else set()
    n_ports = (c_cnt or 0) + (a_cnt or 0) if (c_cnt is not None or a_cnt is not None) else (len(inv) if inv and all(re.fullmatch(r"[AC]\d", t) for t in inv) else None)
    full = sorted({ws[0] for n, ws, _ in o.in_use if n_ports and n == n_ports and len(set(ws)) == 1})
    combos = [(n, re.sub(r"(\+\s*\d+(?:\.\d+)?\s*W)\s*Max\b", r"\1", re.sub(r"(\d(?:\.\d+)?\s*W)\s*Max\b(?=\s*\+)", r"\1", v))) for n, v in o.combos]   # '40W Max + 12W Max' is additive
    t, toks, why = P.all_port_total([p["name"] for p in ports], combos) if combos else (None, None, None)
    if len(full) == 1:
        lit_ = next(l for n, ws, l in o.in_use if n == n_ports)
        add("out.all_ports_w", full[0], lit_, "N ports in use", quote=f"all {n_ports} printed ports in use")
    elif t is not None:
        add("out.all_ports_w", t, "; ".join(f"{n}: {v}" for n, v in o.combos), "output rows", quote="all-ports output: " + " + ".join(toks or []))
    elif why or o.in_use:
        add("out.all_ports_w", P.Unresolved(why or f"'ports in use' rows do not match the printed port count ({n_ports})"), lit, "output rows")
    pr.fingerprints.setdefault("labels", labels)
    pr.fingerprints.setdefault("unmapped", unmapped)


def dims(text):
    d = P.dims_mm(text)
    if d:
        return d
    t = (text or "").replace("×", "x").replace("*", "x")
    m = re.search(NUM + r"\s*x\s*" + NUM + r"\s*x\s*" + NUM + r"\s*cm\b", t, re.I)
    if m:
        return {"w": P.fnum(round(float(m[1]) * 10, 1)), "d": P.fnum(round(float(m[2]) * 10, 1)), "h": P.fnum(round(float(m[3]) * 10, 1)), "unit": "mm"}
    m = re.search(NUM + r"\s*(?:in\b|\"|”)?\s*x\s*" + NUM + r"\s*(?:in\b|\"|”)?\s*x\s*" + NUM + r"\s*(?:inches|inch|in\b|\"|”)", t, re.I)
    if m:
        return {"w": round(float(m[1]) * 25.4, 1), "d": round(float(m[2]) * 25.4, 1), "h": round(float(m[3]) * 25.4, 1), "unit": "mm"}
    return None


def grams(text):
    t = text or ""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", t, re.I)
    if m:
        return P.fnum(m[1])
    m = re.search(r"(\d*\.?\d+)\s*(?:oz|ounces?)\b", t, re.I)
    if m:
        return round(float(m[1]) * 28.3495, 1)
    m = re.search(r"(\d*\.?\d+)\s*(?:lbs?|pounds?)\b", t, re.I)
    return round(float(m[1]) * 453.592, 1) if m else None


# ---------------------------------------------------------------- Shopify store pages
def parse_store(ad, snap, page, prod):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [source(snap, f"{ad.brand_name} US store page {key}")]
    title = clean(prod.get("title")) or snap.ref.hints.get("title") or key
    kind = charger_kind(title + " " + key.replace("-", " "))
    if kind is None:
        pr.absences.append({"key": "*", "reason": f"not a single charger model page ({title[:60]})", "source": "s1"})
        return pr
    rows = page_rows(page, prod.get("body_html") or "")
    skus = [(v.get("sku") or "").strip() for v in prod.get("variants") or [] if (v.get("sku") or "").strip()]
    rowd = {lab: " ".join(ls) for lab, ls in reversed(rows)}
    model, basis = ad.model_of(rowd, skus, title, key)
    if model and re.search(r"\d[A-Z]?(?:EU|UK|AU|JP|KR)$", model):        # CUKTECH 'Model: A15CEU' = the EU build
        model, basis = None, f"model {model} carries a non-US market suffix"
    if not model:
        pr.absences.append({"key": "*", "reason": f"no model number ({basis})", "source": "s1"})
        pr.fingerprints = {"labels": [r[0] for r in rows], "title": title, "skus": skus}
        return pr
    gt = [str(v["barcode"]) for v in prod.get("variants") or [] if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"]))]
    identity(pr, ad.brand, model, title, [(s, None) for s in skus], gt, basis)
    colors = []
    for o in prod.get("options") or []:
        if o.get("name", "").lower() in ("color", "colour"):
            colors += [x for x in o.get("values") or [] if x.lower() != "default title"]
    read_rows(pr, ad.adapter, snap, model, title, kind, rows, colors=colors, table="store spec rows")
    v0 = next((v for v in prod.get("variants") or [] if v.get("price")), None)
    if v0:
        emit(pr, ad.adapter, snap, model, "id.msrp_us", float(v0["price"]), f"${v0['price']} ({v0.get('sku')}) at fetch", "variant price")
    pr.fingerprints.update({"raw": snap.snapshot, "model_basis": basis})
    return pr
