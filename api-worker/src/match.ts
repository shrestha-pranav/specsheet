// Title -> product matcher: a faithful port of scripts/match.py `match()` (the reference implementation; read its docstring for the
// rules). Precision first: no answer beats a wrong answer. The catalogue side arrives pre-tokenised by Python (api-worker/pack/match/
// catalogue.json, "specsheet.match/1", built by scripts/build_r2.py match_catalogue()), so only TITLES are tokenised here.
//
// Python `re` semantics are reproduced on purpose: every regex uses the `u` flag; Python's Unicode \b, \d, \s are spelled out (B, D, S
// below) because JS's are ASCII-only / a different whitespace set; Python `.` is [^\n] and a non-MULTILINE `$` is (?=\n?$). Parity with
// match.py is asserted by test/match-parity.test.ts. Self-contained on purpose: no imports from the rest of src.

export interface MatchCandidate {
  id: string; category: string; brand: string; name: string; basis: string; confidence: number; evidence: Record<string, unknown>;
}

/** [id, category, brand, brand_id, name, toks (sorted), btoks (sorted), tokens(phrase) per phrase (phrases[0] = name), multipack_ok] */
export type CatalogueProduct = [string, string, string, string, string, string[], string[], string[][], number];

export interface CatalogueDoc {
  format: string;
  products: CatalogueProduct[];
  brand_names: Record<string, string[]>;
  ident: Record<string, string[]>;
  aliases: Record<string, string[]>;
  mod_by_brand: Record<string, string[]>;
}

// ---------------------------------------------------------------- Python-re building blocks
const W = String.raw`[\p{L}\p{N}_]`;                                   // Python str \w (isalnum() or '_')
const B = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;                   // Python Unicode \b
const D = String.raw`\p{Nd}`;                                          // Python str \d
const SC = String.raw`\t\n\v\f\r \x1c-\x1f\x85\xa0  -     　`;  // str.isspace()
const S = `[${SC}]`;                                                   // Python str \s
const rx = (src: string, flags = "") => new RegExp(src, "u" + flags);

const GENERIC = new Set(`charger chargers wall usb c a type port ports fast charging charge adapter adapters power block plug with and for the of in to gan pd
3.0 3.1 delivery compact foldable travel desktop station brick cube laptop phone iphone samsung galaxy pixel ipad macbook new official edition
black white gray grey blue silver green pink red purple beige graphite space cream starlight portable ssd internal external solid
state drive nvme pcie m.2 m 2 sata 2.5 gen4 gen5 gen3 x4 tv smart led uhd 4k qled oled hdr monitor display gaming inch class series model
retractable cable built included kit set w wh v a`.split(/\s+/).filter(Boolean));
const MODIFIERS = new Set("ii iii iv v vi pro max plus ultra mini lite air slim prime neo se elite evo duo trio go flex next uno core nano".split(" "));
const NEXT_VARIANT = new Set([...MODIFIERS, "ii", "iii"]);
const RETAILERS = "amazon|best ?buy|walmart|target|newegg|b&h|costco|ebay|woot|micro center|bj'?s|sam'?s club|home depot|lowe'?s|staples|adorama";
const CATS: [string, RegExp][] = ([
  ["power-banks", "power ?bank|portable charger|battery pack|magsafe battery"],
  ["power-stations", "power station|solar generator"],
  ["chargers", `${B}charger${B}|charging station|power adapter|wall adapter|${B}gan${B}`],
  ["ssds", `${B}ssd${B}|nvme|solid state`],
  ["monitors", `${B}monitor${B}`],
  ["tvs", `${B}tv${B}|television|${B}qled${B}|${B}oled tv${B}|roku tv|google tv|fire tv`],
  ["laptops", `${B}laptop${B}|notebook|chromebook|thinkpad|ideapad|zenbook|vivobook`],
  ["routers", "router|mesh wi-?fi|wifi system"],
  ["robot-vacuums", "robot vacuum|robovac|roomba"],
  ["air-purifiers", "air purifier"],
  ["power-strips", "surge protector|power strip"],
] as [string, string][]).map(([c, s]) => [c, rx(s, "i")]);

const CLEAN_PRICE = rx(String.raw`\$${S}?${D}[${D},]*(?:\.${D}{1,2})?|${B}${D}{1,3}%${S}*off${B}|${B}save${S}+\$?${D}+${B}`, "gi");
const CLEAN_RETAILER = rx(`${S}(?:at|@|from|via)${S}+(?:${RETAILERS})${B}[^\\n]*(?=\\n?$)`, "gi");
const CLEAN_DEAL = rx(`${B}(?:deal|lowest price|all-time low|price drop|clearance|coupon|w/ code|with code|free shipping|prime members?)${B}`, "gi");

const T_PORT = rx(`(${D})${S}*-?${S}*ports?${B}`, "g");
const T_INCH = rx(`(${D})${S}*-?${S}*(?:inch(?:es)?|in${B}|"|-in${B})`, "g");
const T_CLASS = rx(`(${D})${S}*-?${S}*(?:class)${B}`, "g");
const T_UNIT = rx(String.raw`(${D}+(?:\.${D}+)?)${S}*(w|tb|gb|mah|wh|hz)${B}`, "g");
const T_KMAH = rx(`${B}(${D}{1,2})k${S}*mah${B}|${B}(${D}{1,2})k${B}(?=[^\\n]*${B}(?:power ?bank|mah)${B})`, "g");
const T_FIND = /[a-z0-9]+(?:\.[0-9]+)?/g;

const ATTR_RX: [string, RegExp][] = [
  ["w", /^(\d+(?:\.\d+)?)w$/], ["tb", /^(\d+(?:\.\d+)?)tb$/], ["gb", /^(\d+)gb$/], ["mah", /^(\d+)mah$/], ["in", /^(\d{2,3})in$/], ["port", /^(\d)port$/],
];   // run over [a-z0-9.] tokens only, so ASCII \d == Python \d here
const MODEL_TOK = /(?<![A-Za-z0-9])([A-Za-z0-9][A-Za-z0-9\-./#]{2,}[A-Za-z0-9])(?![A-Za-z0-9])/gu;
const MODEL_NEXT = rx(`${S}+([A-Za-z]{2,6})${B}(?:${S}+([A-Za-z]{2,6})${B})?`, "y");   // Python re.match on title[m.end():]
const WORD_AFTER = rx(`${S}+([A-Za-z]+)`, "y");
const NORM_ID = rx(`[${SC}.\\-]`, "g");
const STRIP_DOTS = /^[./-]+|[./-]+$/g;
const MULTIPACK = rx(`${B}(?:[2-9]|two|three|four)${S}*-?${S}*(?:pack|pk|count|ct)${B}|${B}pack of [2-9]${B}|${B}[2-9]${S}*x${S}+(?!usb)`, "i");
const GTIN = /^(?:\d{8}|\d{12,14})$/;
const HAS_DIGIT = /\d/;
const HAS_LETTER = /[A-Za-z]/;
const THREE_DIGITS = /^\d{3}$/;
const ALL_DIGITS = /^\d+$/;   // nv is ASCII (model tokens are [A-Za-z0-9...]), so str.isdigit() == this

// ---------------------------------------------------------------- text (match.py clean_title / tokens / attrs / norm_id / model_tokens)
export function cleanTitle(t: string | null | undefined): string {
  return (t || "").replace(CLEAN_PRICE, " ").replace(CLEAN_RETAILER, " ").replace(CLEAN_DEAL, " ");
}

export function tokens(input: string | null | undefined): string[] {
  let s = (input || "").toLowerCase().replaceAll("″", '"').replaceAll("”", '"').replaceAll("“", '"').replaceAll("’", "'");
  s = s.replace(T_PORT, "$1port");
  s = s.replace(T_INCH, "$1in");
  s = s.replace(T_CLASS, "$1in");
  s = s.replace(T_UNIT, "$1$2");
  s = s.replace(T_KMAH, (_m: string, a?: string, b?: string) => `${a || b}000mah`);
  return s.match(T_FIND) || [];
}

type Attrs = Map<string, Set<number>>;

function attrs(toks: Iterable<string>): Attrs {
  const a: Attrs = new Map();
  for (const t of toks) {
    for (const [k, r] of ATTR_RX) {
      const m = r.exec(t);
      if (m) {
        let set = a.get(k);
        if (!set) a.set(k, (set = new Set()));
        set.add(parseFloat(m[1]));
      }
    }
  }
  const gb = a.get("gb");
  if (gb) {              // 2000GB == 2TB; like Python's setdefault, the "tb" key exists (maybe empty) whenever "gb" does
    let tb = a.get("tb");
    if (!tb) a.set("tb", (tb = new Set()));
    for (const x of gb) if (x >= 1000) tb.add(x / 1000);
  }
  return a;
}

const normId = (v: string) => v.toUpperCase().replace(NORM_ID, "");

function modelTokens(title: string): string[] {
  const out: string[] = [];
  for (const m of title.matchAll(MODEL_TOK)) {
    const t = m[1].replace(STRIP_DOTS, "");
    if (HAS_DIGIT.test(t) && (HAS_LETTER.test(t) || t.length >= 5)) {
      out.push(t);
      if (t.includes("/")) out.push(t.split("/")[0]);
      MODEL_NEXT.lastIndex = m.index + m[0].length;
      const nxt = MODEL_NEXT.exec(title);
      if (nxt) {
        out.push(`${t} ${nxt[1]}`);
        if (nxt[2]) out.push(`${t} ${nxt[1]} ${nxt[2]}`);
      }
    }
  }
  return [...new Set(out)];
}

export function titleCategory(text: string): string | null {
  for (const [cat, r] of CATS) if (r.test(text)) return cat;
  return null;
}

export const isMultipack = (text: string): boolean => MULTIPACK.test(text);

const round2 = (x: number) => Number(x.toFixed(2));
const own = <T>(o: Record<string, T>, k: string): T | undefined => (Object.hasOwn(o, k) ? o[k] : undefined);
const sorted = (xs: Iterable<string>) => [...xs].sort();
const pyFloat = (x: number) => (Number.isInteger(x) && Math.abs(x) < 1e16 ? x.toFixed(1) : String(x));
const pyNums = (xs: Iterable<number>) => `[${[...xs].sort((a, b) => a - b).map(pyFloat).join(", ")}]`;   // Python repr(sorted(set of floats))
const pyStrs = (xs: Iterable<string>) => `[${sorted(xs).map((x) => `'${x}'`).join(", ")}]`;              // repr(sorted(...)) of [a-z0-9_.] words

// ---------------------------------------------------------------- matcher
interface Product {
  id: string; category: string; brand: string; brandId: string; name: string;
  toks: Set<string>; attrs: Attrs; mods: Set<string>; multipackOk: boolean;
}

interface Phrase {
  p: Product;
  uniq: string[];     // set(tokens(phrase))
  dist: string[];     // set(pt) - GENERIC - btoks; never empty (such phrases can match neither basis, so they are not indexed)
  partOk: boolean;    // len(dist) >= 2 and some dist token has a digit or is a MODIFIER
}

const EMPTY = new Set<string>();

export class Matcher {
  readonly products: Map<string, Product>;
  private brandNames: Map<string, string[]>;
  private maxBrandWords: number;
  private ident: Record<string, string[]>;
  private aliases: Record<string, string[]>;
  private phraseIndex: Map<string, Phrase[]>;   // rarest distinctive token -> phrases (a phrase can only match if its dist set <= title tokens)

  constructor(doc: CatalogueDoc) {
    if (!doc || doc.format !== "specsheet.match/1") throw new Error(`unsupported match catalogue format: ${doc && doc.format}`);
    this.ident = doc.ident;
    this.aliases = doc.aliases;
    this.brandNames = new Map(Object.entries(doc.brand_names));
    this.maxBrandWords = 0;
    for (const n of this.brandNames.keys()) this.maxBrandWords = Math.max(this.maxBrandWords, n.split(" ").length);
    const modsByBrand = new Map<string, Set<string>>();
    for (const [b, ms] of Object.entries(doc.mod_by_brand)) modsByBrand.set(b, new Set(ms));
    this.products = new Map();
    const phrases: Phrase[] = [];
    const df = new Map<string, number>();
    for (const [id, category, brand, brandId, name, toks, btoks, phraseToks, mp] of doc.products) {
      const p: Product = { id, category, brand, brandId, name, toks: new Set(toks), attrs: attrs(toks), mods: modsByBrand.get(brandId) || EMPTY, multipackOk: !!mp };
      this.products.set(id, p);
      const bt = new Set(btoks);
      for (const pt of phraseToks) {
        if (!pt.length) continue;
        const uniq = [...new Set(pt)];
        const dist = uniq.filter((t) => !GENERIC.has(t) && !bt.has(t));
        if (!dist.length) continue;
        phrases.push({ p, uniq, dist, partOk: dist.length >= 2 && dist.some((t) => HAS_DIGIT.test(t) || MODIFIERS.has(t)) });
        for (const t of dist) df.set(t, (df.get(t) || 0) + 1);
      }
    }
    this.phraseIndex = new Map();
    for (const ph of phrases) {
      let key = ph.dist[0];
      for (const t of ph.dist) if (df.get(t)! < df.get(key)!) key = t;
      let l = this.phraseIndex.get(key);
      if (!l) this.phraseIndex.set(key, (l = []));
      l.push(ph);
    }
  }

  /** Python Catalogue.brands_in: f" {n} " in the space-joined title tokens. Names are space-joined tokens, so that is n-gram equality. */
  private brandsIn(toks: string[]): Set<string> {
    const out = new Set<string>();
    for (let i = 0; i < toks.length; i++) {
      let n = "";
      for (let k = 0; k < this.maxBrandWords && i + k < toks.length; k++) {
        n = k ? `${n} ${toks[i + k]}` : toks[i];
        const bs = this.brandNames.get(n);
        if (bs) for (const b of bs) out.add(b);
      }
    }
    return out;
  }

  private attrConflict(p: Product, tattrs: Attrs): string | null {
    const pa = p.attrs;
    for (const k of ["w", "tb", "mah", "in", "port"]) {
      const a = pa.get(k), b = tattrs.get(k);
      if (a && b && ![...a].some((x) => b.has(x))) return `${k} differs (${pyNums(a)} vs title ${pyNums(b)})`;
    }
    const a = pa.get("gb"), b = tattrs.get("gb");
    if (a && b && ![...a].some((x) => b.has(x)) && !pa.has("tb")) return "capacity differs";
    return null;
  }

  private variantConflict(p: Product, ttoks: string[]): string | null {
    const extra = new Set<string>();
    for (const t of ttoks) {
      if (!p.toks.has(t) && (THREE_DIGITS.test(t) || t === "ii" || t === "iii" || t === "iv" || (MODIFIERS.has(t) && p.mods.has(t)))) extra.add(t);
    }
    return extra.size ? `title asserts ${pyStrs(extra)}, which this product's names do not carry` : null;
  }

  private guards(p: Product, ttoks: string[], tattrs: Attrs, brands: Set<string>, tcat: string | null, cat: string | undefined,
                 attributes: boolean, multipack: boolean): string | null {
    if (cat && p.category !== cat) return "category filter";
    if (multipack && !p.multipackOk) return "title is a multipack listing (a package), the product is a single unit";
    if (brands.size && !brands.has(p.brandId)) return `title names brand ${pyStrs(brands)}`;
    if (tcat && p.category !== tcat) return `title names category ${tcat}`;
    if (!attributes) return null;
    return this.attrConflict(p, tattrs) || this.variantConflict(p, ttoks);
  }

  match(title: string, category?: string, diag?: Record<string, unknown>): MatchCandidate[] {
    const raw = cleanTitle(title);
    const ttoks = tokens(raw);
    const tset = new Set(ttoks);
    const tattrs = attrs(ttoks);
    const brands = this.brandsIn(ttoks);
    const tcat = titleCategory(raw);
    const mp = isMultipack(raw);
    const d = diag ?? {};
    d.brands = sorted(brands);
    d.title_category = tcat;
    const finish = (p: Product, basis: string, confidence: number, evidence: Record<string, unknown>): MatchCandidate[] =>
      [{ id: p.id, category: p.category, brand: p.brand, name: p.name, basis, confidence, evidence }];

    // 1. exact model number / identifier
    const hits = new Map<string, string[]>(), rej: Record<string, string> = {};
    for (const tok of modelTokens(raw)) {
      const nv = normId(tok);
      const keys = ["mfr_model", "mtm", "mfr_sku"].map((s) => `${s}:${nv}`);
      if (GTIN.test(nv)) keys.push(`gtin:${nv.padStart(14, "0")}`);
      const ids = new Set<string>();
      for (const k of keys) for (const i of own(this.ident, k) || []) ids.add(i);
      if (HAS_DIGIT.test(tok)) {
        const tt = tokens(tok);
        if (tt.length === 1) for (const i of own(this.aliases, tt[0]) || []) ids.add(i);
      }
      for (const i of ids) {
        const p = this.products.get(i);
        if (!p) continue;
        if (ALL_DIGITS.test(nv) && nv.length < 8 && !brands.has(p.brandId)) { rej[i] = `bare number ${tok} without the brand`; continue; }
        let why = this.guards(p, ttoks, tattrs, brands, tcat, category, false, mp);
        let nxt: RegExpExecArray | null = null;
        const at = raw.indexOf(tok);
        if (at >= 0) { WORD_AFTER.lastIndex = at + tok.length; nxt = WORD_AFTER.exec(raw); }
        if (!why && nxt && NEXT_VARIANT.has(nxt[1].toLowerCase()) && !p.toks.has(nxt[1].toLowerCase())) {
          why = `the word after ${tok} ('${nxt[1]}') names a variant this product does not carry`;   // 'RT-AX88U Pro' is not RT-AX88U
        }
        if (why) { rej[i] = why; continue; }
        let h = hits.get(i);
        if (!h) hits.set(i, (h = []));
        h.push(tok);
      }
    }
    if (hits.size) {
      d.model_hits = Object.fromEntries(hits);
      if (hits.size === 1) {
        const [i, toks] = hits.entries().next().value!;
        const p = this.products.get(i)!;
        let conf = brands.has(p.brandId) ? 0.97 : 0.9;
        const ev: Record<string, unknown> = { tokens: toks };
        const c = this.attrConflict(p, tattrs);
        if (c) { conf = round2(conf - 0.15); ev.conflict = `identifier matches but the catalogue name disagrees: ${c}`; }
        return finish(p, "exact_model_number", conf, ev);
      }
      d.ambiguous = `identifier tokens name ${hits.size} products`;
      return [];
    }
    if (Object.keys(rej).length) d.model_rejected = rej;

    // 2/3. alias phrases. Only phrases whose rarest distinctive token is in the title can satisfy `dist <= tset` (which both bases
    // require), so the inverted index visits exactly the phrases Python's full scan could accept.
    const best = new Map<Product, { full: number; part: number }>();
    for (const t of tset) {
      const l = this.phraseIndex.get(t);
      if (!l) continue;
      for (const ph of l) {
        const p = ph.p;
        if (category && p.category !== category) continue;
        if (brands.size && !brands.has(p.brandId)) continue;
        if (!ph.dist.every((x) => tset.has(x))) continue;
        const full = ph.uniq.every((x) => tset.has(x)) ? ph.uniq.length : 0;
        const part = brands.size && ph.partOk ? ph.dist.length : 0;
        if (!full && !part) continue;
        const b = best.get(p);
        if (!b) best.set(p, { full, part });
        else { b.full = Math.max(b.full, full); b.part = Math.max(b.part, part); }
      }
    }
    const full = new Map<string, number>(), part = new Map<string, number>();
    let aliasRejected: Record<string, string> | undefined;
    for (const [p, b] of best) {
      const why = this.guards(p, ttoks, tattrs, brands, tcat, category, true, mp);
      if (why) { (aliasRejected ??= {})[p.id] = why; continue; }
      if (b.full) full.set(p.id, b.full);
      if (b.part) part.set(p.id, b.part);
    }
    if (aliasRejected) d.alias_rejected = aliasRejected;
    const passes: [string, Map<string, number>, number][] = [["exact_alias", full, 0.88], ["brand_marketing_name", part, 0.72]];
    for (const [basis, pool, conf] of passes) {
      if (!pool.size) continue;
      const top = Math.max(...pool.values());
      const tied = [...pool].filter(([, n]) => n === top).map(([i]) => i);
      if (tied.length === 1) {
        return finish(this.products.get(tied[0])!, basis, top >= 3 ? conf : round2(conf - 0.1), { matched_tokens: top });
      }
      d.ambiguous = `${basis}: ${tied.length} products tie (${sorted(tied).slice(0, 5).join(", ")})`;
      return [];
    }
    return [];
  }
}

const cache = new WeakMap<CatalogueDoc, Matcher>();

/** One Matcher per catalogue document object (the constructor builds the indexes; reuse it across requests on a warm isolate). */
export function loadMatcher(doc: CatalogueDoc): Matcher {
  let m = cache.get(doc);
  if (!m) cache.set(doc, (m = new Matcher(doc)));
  return m;
}
