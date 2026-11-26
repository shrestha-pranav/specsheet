#!/usr/bin/env python3
"""Shopify-store portable power station adapters v1 (contract ARCHITECTURE 15.5), category power-stations: EcoFlow (us.ecoflow.com), BLUETTI
(www.bluettipower.com), Jackery (www.jackery.com), Goal Zero (www.goalzero.com). One module, one class per source; fetch is inherited from
shopify_powerbanks._Shop unchanged (product page HTML + /products/<handle>.json in one gzip JSON blob, 1 req/s per host, crawler UA).

discover : {base}/products.json (public Shopify catalogue; robots allow /products) -> per-brand predicate: power stations only. Pages that are
           packages by title (Solar Generator, Kit, '+', Bundle, Refurbished / Open Box, Extra Battery, Inverter-only modules, deposits) are
           not discovered: a station bundled with panels or a battery is a package, never the station model.
parse    : pure. Labelled spec rows from each theme's spec markup (never marketing prose), mapped by _powerstation.emit_rows():
           EcoFlow   'pdp-specs-title' / 'pdp-specs-content' under h2 'Specs' (a 'Specs - <name>' block naming another product = absence).
           BLUETTI   uk-grid label/value rows under h4 sections (BATTERY INFO / OUTPUT / INPUT / RECHARGE TIME / GENERAL).
           Jackery   per-variant spec blocks (div variant_id=..) with one drop-down per item; only the drop-down whose heading names the station
                     is read. Blocks of different variants are kept apart and a 230 V block (another market's unit copied onto the US page)
                     is skipped. Disagreeing US blocks become separate claims (conflict), never a pick.
           Goal Zero accordion 'GENERAL / PORTS / BATTERY DETAILS / RECHARGE CHARGE TIMES' li 'Label: value' lines (the image banner block is
                     ignored: on the Yeti 1500X it says 'Chainable: With Yeti Link' while the accordion says 'Chainable: No').
Identity : EcoFlow   the manufacturer SKU stem of the page's unit-only variants (EFDELTA3P from EFDELTA3P-US; ZMR620 from ZMR620-B-US): region and
                     colour suffix stripped. >1 stem (RIVER mini Standard vs Wireless, '... Series' pages) = absence.
           BLUETTI   SKU stem before the market token (AC180P from AC180P-UN-GY-ID-SPFUS-00; EL30V2 from EL30V2-US-PK-ID-SPFUS-00). Bundle SKUs
                     (AC180P-2-62-SPFUS-00: model-<n>-<code>) are packages, not aliases.
           Jackery   no label model (JE-1000D) is printed: the station name in the spec drop-down heading ('Explorer 1000 v2'), colour suffix
                     stripped; unit-only variant item numbers (21-0001-000220) are colour-SKU aliases.
           Goal Zero the 5-digit item number of the single variant (36300), which must equal the accordion 'SKU:' row (else absence).
"""
import gzip, html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import _contract as C
import _lt as L
import _powerbank as P
import _powerstation as PS
import _run
import shopify_powerbanks as S

VERSION = 9       # v9 (A3-fix review-10 P1-3): _powerstation repeated-unit alternatives after the figure ('10 ms or 20 ms', '10 ms / 20 ms') and trailing lower bounds ('or over', 'or above', 'and over', '=>', '&ge;') -> unresolved, never exact, rows and prose; v8 (A3-fix review-9 P1-3): _powerstation trailing bounds ("20 ms maximum", "or less") -> up to N; "between 10 and 20" ranges, lower bounds (≥, at least, or more) and approx qualifiers -> unresolved, never exact; v7 (A3-fix review-8): _powerstation UPS "up to N" kept, ranges / two figures never an endpoint, exact prose model identity; v6 (A2-dell r6): _powerstation labelled UPS row bound (＜/≤/</under/within) -> "up to N"; v5 (A2-mon r5b): _powerstation capacity row also matches "Battery Pack Capacity" (Goal Zero); v4 (A2-mon r5): _powerstation chemistry reads LiFePO\u2084; ups.switchover_ms from product-description prose under the coordinator ruling (single model, not a package, UPS/switchover + N ms, <-bounds = up to); v3: r7 shared _powerbank changed; station rules unchanged; v2: r6 shared _powerbank changed (repeated port row = one port); station rules unchanged
CATEGORIES = {"power-stations"}
DELAY = 1.0
PKG_TITLE = re.compile(r"\+|&|solar generator|\bkit\b|bundle|combo|refurb|open box|extra battery|expansion|add-on|deposit|\binverter\b|"
                       r"subscriber|members|gift|warranty|cart\b|trolley|bag\b|cable|adapt|panel|charger\b|replacement|fridge|cooler|"
                       r"home backup solar|power supply|module|double kit|\(\d+\s*kwh\)", re.I)
UNIT_VARIANT_BAD = re.compile(r"\+|×|\bx\s*\d|\d\s*x\b|solar|panel|battery|bag\b|charger|kit\b|cable|members|bundle|cart|trolley|hub|"
                              r"generator|alternator|\b2\s*×|double|eco ?credits|gift|warranty", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", html.unescape(s or "").lower())


class _Station(S._Shop):
    version, categories = VERSION, CATEGORIES

    def keep(self, p):
        return False

    def discover(self, checkpoint, net):
        refs, page, n = [], 1, 0
        while page <= 10:
            r = net.get(f"{self.base}/products.json?limit=250&page={page}", DELAY)
            if not hasattr(r, "status_code") or r.status_code != 200:
                return C.Discovery(refs, False, f"products.json page {page}: {getattr(r, 'status_code', r)}", {"page": page})
            ps = r.json().get("products") or []
            if not ps:
                break
            n += len(ps)
            for p in ps:
                if self.keep(p):
                    refs.append(C.Ref(self.source_id, p["handle"], f"{self.base}/products/{p['handle']}", {"title": p.get("title")}))
            page += 1
        return C.Discovery(refs, True, None, {"catalogue": n, "products": len(refs)})

    def parse(self, snap, blobs, profile):
        d = json.loads(gzip.decompress(blobs.read(snap.snapshot, ".json.gz")))
        return parse_station(self, snap, d["page"], d.get("product") or {})

    # -> (model or None, reason, [unit variants], [package variants])
    def identity(self, prod, page, blocks):
        return None, "not implemented", [], []

    # -> [(block_name, {label: value})] ; reason when none usable
    def blocks(self, page, prod, title):
        return [], "not implemented"


def _variants(prod):
    return [v for v in prod.get("variants") or [] if (v.get("sku") or "").strip()]


class EcoflowStations(_Station):
    id, source_id, base, brand = "ecoflow_stations", "ecoflow-us-stations", "https://us.ecoflow.com", "ecoflow"

    def keep(self, p):
        t = p.get("title") or ""
        return bool(re.search(r"power station", t, re.I)) and not PKG_TITLE.search(t) and not re.search(r"refurb|bundle", p.get("product_type") or "", re.I)

    @staticmethod
    def stem(sku):
        s = sku.strip().upper()
        s = re.sub(r"-(US|AM|USAMZ)(-.*)?$", "", s)
        s = re.sub(r"-(B|W|G|S|DG|GR|GY|BK|WH|BLU|L)$", "", s)
        return s

    def identity(self, prod, page, blocks):
        unit, pkg = [], []
        for v in _variants(prod):
            (pkg if UNIT_VARIANT_BAD.search(v.get("title") or "") or "+" in v["sku"] else unit).append(v)
        stems = {self.stem(v["sku"]) for v in unit}
        if len(stems) != 1:
            return None, (f"{len(stems)} unit-variant SKU stems ({', '.join(sorted(stems))[:80]}): page sells several models" if stems else "no unit-only variant"), unit, pkg
        return stems.pop(), None, unit, pkg

    def blocks(self, page, prod, title):
        m = re.search(r"<h2>\s*(?:Specs|Specifications|Tech Specs)\s*(?:-\s*(.*?))?</h2>(.*?)</section>", page, re.S)
        if not m:
            return [], "no pdp-specs section"
        if m[1] and norm(m[1]) not in norm(title):
            return [], f"spec section names another product: {P.clean(m[1])[:80]}"
        rows = {}
        for lab, val in re.findall(r'pdp-specs-title">(.*?)</p>.*?pdp-specs-content">(.*?)</div>', m[2], re.S):
            rows.setdefault(P.clean(lab), PS.txt(val))
        return ([("Specs", rows)] if rows else []), (None if rows else "empty spec section")


class BluettiStations(_Station):
    id, source_id, base, brand = "bluetti_stations", "bluetti-us-stations", "https://www.bluettipower.com", "bluetti"

    def keep(self, p):
        t, ty = p.get("title") or "", p.get("product_type") or ""
        return bool(re.search(r"power station", t + " " + ty, re.I)) and bool(re.search(r"power station", t, re.I)) and not PKG_TITLE.search(t)

    def identity(self, prod, page, blocks):
        unit, pkg, stems = [], [], set()
        for v in _variants(prod):
            m = re.match(r"^([A-Z0-9]+?)-(US|UN)-", v["sku"].strip().upper())
            if m and not UNIT_VARIANT_BAD.search(v.get("title") or ""):
                unit.append(v); stems.add(m[1])
            else:
                pkg.append(v)
        if len(stems) != 1:
            return None, (f"{len(stems)} unit SKU stems ({', '.join(sorted(stems))[:80]})" if stems else "no unit-only variant SKU (MODEL-US-/-UN-)"), unit, pkg
        return stems.pop(), None, unit, pkg

    def blocks(self, page, prod, title):
        page = re.sub(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>", " ", page, flags=re.S)
        heads = [(m.start(), P.clean(m[1])) for m in re.finditer(r'<h4 class="uk-text-600[^"]*">([^<]+)</h4>', page)]
        rows = {}
        for m in re.finditer(r'<span class="uk-h5 uk-text-500 uk-margin-remove">\s*(.*?)\s*</span>\s*</div>\s*<div class="uk-width-expand">\s*<span>(.*?)</span>', page, re.S):
            sec = next((h for pos, h in reversed(heads) if pos < m.start()), "")
            lab = P.clean(m[1]).rstrip(":").strip()
            rows.setdefault(f"{sec} / {lab}" if sec else lab, PS.txt(m[2]))
        return ([("Specs", rows)] if rows else []), (None if rows else "no spec rows in the HTML (newer template renders Tech Specs client-side)")


class JackeryStations(_Station):
    id, source_id, base, brand = "jackery_stations", "jackery-us-stations", "https://www.jackery.com", "jackery"
    STATION = re.compile(r"^(?:Jackery\s+)?((?:Explorer|HomePower|E)\s*\d{3,5}[A-Za-z]*(?:\s+(?:Plus|Pro|Max|Ultra|v\d))*(?:\s+(?:Plus|Pro|Max|Ultra|v\d))*)"
                         r"(?:\s+Portable Power Station)?\s*(?:\((?:[A-Za-z ]+)\))?$", re.I)

    def keep(self, p):
        t = p.get("title") or ""
        return bool(re.search(r"explorer|homepower|power station", t, re.I)) and not re.search(r"\+|add-on|warranty|trolley|hat\b|bottle|double kit|"
                                                                                          r"transfer switch|gift|sticker|cup\b|printer|refurb|cover|case\b|edition", t, re.I)

    def station_name(self, head):
        m = self.STATION.match(P.clean(head))
        if not m:
            return None
        n = re.sub(r"\s+", " ", m[1]).strip()
        return re.sub(r"(?i)^homepower", "HomePower", re.sub(r"(?i)^explorer", "Explorer", n))

    def blocks(self, page, prod, title):
        vt = {str(v["id"]): v for v in prod.get("variants") or []}
        out, skipped = [], []
        ms = list(re.finditer(r'<div variant_id="(\d+)" class="pdp-specs-v5-specs-variant[^"]*">', page))
        for i, m in enumerate(ms):
            seg = page[m.end(): ms[i + 1].start() if i + 1 < len(ms) else m.end() + 400000]
            drops = list(re.finditer(r'<span class="text-overflow-1[^"]*">([^<]+)</span>', seg))
            for j, d in enumerate(drops):
                name = self.station_name(d[1])
                if not name:
                    continue
                body = seg[d.end(): drops[j + 1].start() if j + 1 < len(drops) else len(seg)]
                rows, sec = {}, ""
                for u in re.finditer(r'<div [^>]*class="lg:text-2xl[^"]*font-semibold">([^<]+)</div>|<span [^>]*class="key[^"]*">(.*?)</span>\s*<span [^>]*class="value[^"]*">(.*?)</span>', body, re.S):
                    if u[1]:
                        sec = P.clean(u[1]); continue
                    rows.setdefault(f"{sec} / {P.clean(u[2])}", PS.txt(u[3]))
                v = vt.get(m[1]) or {}
                ac = " ".join(x for k, x in rows.items() if re.search(r"ac output", k, re.I))
                if re.search(r"\b2[23]0\s*V", ac) and not re.search(r"\b1[12]0\s*V", ac):
                    skipped.append(f"variant {v.get('sku') or m[1]}: 230 V spec block (another market's unit)")
                    continue
                if rows:
                    out.append((f"{name} [{v.get('sku') or m[1]}]", rows))
        return out, ("; ".join(skipped) if not out and skipped else None if out else "no station spec block")

    def identity(self, prod, page, blocks):
        names = {re.sub(r"\s*\[.*$", "", b) for b, _ in blocks}
        unit, pkg = [], []
        for v in _variants(prod):
            (pkg if UNIT_VARIANT_BAD.search(v.get("title") or "") or "+" in (v.get("title") or "") else unit).append(v)
        if len(names) != 1:
            return None, (f"{len(names)} stations in the spec blocks ({', '.join(sorted(names))[:80]})" if names else "no station spec block"), unit, pkg
        return names.pop(), None, unit, pkg


class GoalzeroStations(_Station):
    id, source_id, base, brand = "goalzero_stations", "goalzero-us-stations", "https://www.goalzero.com", "goal_zero"

    def keep(self, p):
        t, ty = p.get("title") or "", p.get("product_type") or ""
        return (ty == "Portable Power Station" or bool(re.search(r"^(NEW )?Yeti [\w ]*(power station)?$", t, re.I))) and \
            not PKG_TITLE.search(t) and not re.search(r"open box|tank|link|cart|plate|latch|mppt|supply|battery\b|case\b", t, re.I)

    def blocks(self, page, prod, title):
        page = re.sub(r"<style.*?</style>|<script.*?</script>|<svg.*?</svg>", " ", page, flags=re.S)
        rows = {}
        for m in re.finditer(r'<h4 [^>]*?class="accordion-heading[^"]*"[^>]*>(.*?)</h4>\s*<div [^>]*?class="accordion-content[^"]*"[^>]*>(.*?)</div>', page, re.S):
            sec, sub = P.clean(m[1]), ""
            for li in re.findall(r"<li[^>]*>(.*?)</li>", m[2], re.S):
                t = P.clean(li)
                if re.fullmatch(r"<strong>.*</strong>", li.strip(), re.S) or (t.isupper() and ":" not in t):
                    sub = t; continue
                if ":" in t:
                    lab, _, val = t.partition(":")
                    rows.setdefault(f"{sec}{' / ' + sub if sub else ''} / {lab.strip()}", val.strip())
        for m in re.finditer(r'<h4 [^>]*?class="functional-specs__column-title[^"]*"[^>]*>(.*?)</h4>(.*?)(?=<h4 [^>]*?class="functional-specs__column-title|$)', page, re.S):
            sec = P.clean(m[1])
            for li in re.findall(r"<li[^>]*>(.*?)</li>", m[2], re.S):
                lm = re.match(r"\s*(?:<a[^>]*>)?\s*<strong>(.*?)</strong>\s*(?:</a>)?\s*(?:<strong>\s*:\s*</strong>)?(.*)$", li, re.S)
                if lm:
                    lab = P.clean(lm[1]).rstrip(":").strip()
                    rows.setdefault(f"{sec} / {lab}", PS.txt(lm[2]).lstrip(": ").strip())
        named = {m[1] for k in rows for m in [re.match(r"(?i)(yeti (?:pro )?\d{3,4}x?)\b", k)] if m}
        if any(norm(n) not in norm(title) for n in named):
            return [], f"spec sections name another product ({', '.join(sorted(named))[:60]}): page is a package"
        return ([("Specs", rows)] if rows else []), (None if rows else "no accordion / functional-specs rows")

    def identity(self, prod, page, blocks):
        vs = _variants(prod)
        skus = {v["sku"].strip() for v in vs}
        if len(skus) != 1 or not re.fullmatch(r"\d{5}", next(iter(skus), "")):
            return None, f"not one 5-digit item number ({', '.join(sorted(skus))[:60]})", vs, []
        sku = skus.pop()
        printed = {v for _, rows in blocks for k, v in rows.items() if re.search(r"/ SKU$", k)}
        if printed and printed != {sku}:
            return None, f"accordion SKU {sorted(printed)} != variant SKU {sku}", vs, []
        return sku, None, vs, []


def parse_station(ad, snap, page, prod):
    pr, key = C.ParseResult(), snap.ref.key
    pr.sources = [L.source(snap, f"{ad.brand.upper()} US store page {key}")]
    title = P.clean(prod.get("title")) or snap.ref.hints.get("title") or key
    blocks, why = ad.blocks(page, prod, title)
    model, mwhy, unit, pkg = ad.identity(prod, page, blocks)
    pr.fingerprints = {"raw": snap.snapshot, "title": title, "blocks": [b for b, _ in blocks],
                       "labels": sorted({k for _, r in blocks for k in r}),
                       "packages": [{"sku": v.get("sku"), "title": v.get("title")} for v in pkg][:40]}
    if re.search(r"discontinued", title, re.I):
        pr.fingerprints["status"] = "DISCONTINUED"
    if not model:
        pr.absences.append({"key": "*", "reason": f"no model identity: {mwhy}", "source": "s1"})
        return pr
    if why and "package" in why:          # a station + battery/panel page: never the station model
        pr.absences.append({"key": "*", "reason": why, "source": "s1"})
        return pr
    pr.identifiers.append(L.ident("mfr_model", model, "model", ad.brand))
    for lm in sorted({v.strip() for _, rows in blocks for k, v in rows.items() if re.search(r"(?i)(^|/ )model$", k) and re.fullmatch(r"[A-Z]{1,4}-?[A-Z0-9-]{3,12}", v.strip())}):
        if lm.upper() != model.upper():
            pr.identifiers.append(L.ident("mfr_label_model", lm.upper(), "model", ad.brand, role="alias"))
    pr.aliases.append({"text": title, "kind": "marketing_name"})
    for v in unit:
        s = v["sku"].strip().upper()
        if s != model.upper():
            pr.identifiers.append(L.ident("mfr_sku", s, "configuration", ad.brand, role="alias", variant=v.get("title")))
        if v.get("barcode") and re.fullmatch(r"\d{12,14}", str(v["barcode"])):
            pr.identifiers.append(L.ident("gtin", str(v["barcode"]), "package", "GS1", role="alias"))
    if why and not blocks:
        PS.emit_ups_prose(pr, ad.adapter, snap, model, prod.get("body_html"), (title,))     # v4: UPS-prose ruling r5 (one model, not a package)
        pr.absences.append({"key": "*", "reason": why, "source": "s1"})
        return pr
    multi = [b for b, rows in blocks if len({m for v in rows.values() for m in re.findall(r"\(([A-Z]{2,4}\d{2,4}[A-Z]{0,2})\)", v)}) > 1]
    if multi:
        pr.absences.append({"key": "*", "reason": "spec block describes several models (values split per '(MODEL)'): not attributable", "source": "s1"})
        pr.fingerprints["multi_model_block"] = True
        return pr
    unmapped = {}
    for name, rows in blocks:
        unmapped.update(PS.emit_rows(pr, ad.adapter, snap, model, rows, name))
    PS.emit_ups_prose(pr, ad.adapter, snap, model, prod.get("body_html"), (title,))         # v4: UPS-prose ruling r5, only if no row wrote it
    pr.claims = list({c["id"]: c for c in reversed(pr.claims)}.values())[::-1]     # identical claims from several variant blocks: one
    pr.fingerprints["unmapped"] = {k: v[:80] for k, v in unmapped.items()}
    return pr


CLASSES = (EcoflowStations, BluettiStations, JackeryStations, GoalzeroStations)

if __name__ == "__main__":
    which = {c.source_id: c for c in CLASSES}
    if len(sys.argv) < 2 or sys.argv[1] not in which:
        raise SystemExit("usage: shopify_powerstations.py <" + "|".join(which) + "> discover|fetch|parse|run")
    _run.main(which[sys.argv.pop(1)]())
