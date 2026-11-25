#!/usr/bin/env python3
"""The ONE reader of data/source-policy.yaml (PM D1.3; team/briefs/pm-2026-11-24-licensing-gate.md). Gates the free static build
(scripts/build.py via v1_publish.py), the Worker query pack (scripts/build_r2.py --tier free) and the paid export (build_r2.py --tier paid).

  load(path=None) -> Policy          validate + load (SystemExit on an invalid file); path default: $SPECSHEET_SOURCE_POLICY,
                                     else <SPECSHEET_ROOT>/data/source-policy.yaml, else the repo's data/source-policy.yaml
  Policy.disposition(url)            {free, paid, licence_grant, withhold_keys, domain, listed}
  Policy.gate(record, tier)          published record -> gated record | None (tier: free | paid)
  Policy.gate_spec(key, spec, tier, url_of, support)   one resolved spec (used by v1_publish before the source table is remapped)
  python3 -I scripts/source_policy.py [check|unlisted DOCS_API]

Gate semantics (per value, per tier): a source the tier disallows, or whose `withhold_keys` contains the key, is removed. The value is
kept iff a REMAINING source independently supports it (its own claim for that key equals the published value: `support`, from the
claims; without `support` the spec's sources[] are trusted to list supporters only, which is what this gate outputs). Otherwise the value
becomes {status: not_published, value: null, sources: []}. A record none of whose own sources is allowed is omitted from the tier.
Every kept sources[] entry carries licence_grant (a value is under our grant iff one of its sources has licence_grant: true).
Expression guard: string values carrying markup or URLs (copied page text) are never published, names lose markup.
"""
import copy, hashlib, json, os, re, sys, urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parent.parent
TIERS = ("free", "paid")
LICENSE = {"license": "ODbL-1.0", "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
           "license_scope": "compilation + values whose sources[] include licence_grant:true; other values are facts with links, not licensed by us"}
TOP_KEYS = {"policy_version", "changelog", "defaults", "record_rules", "sources"}
DEFAULT_KEYS = {"unlisted", "fail_release_on_unlisted"}
RULE_KEYS = {"drop_record_fields", "exclude_demo_records", "exclude_categories", "withheld_status"}
SOURCE_KEYS = {"domain", "match", "kind", "credit", "free", "paid", "licence_grant", "evidence", "withhold_keys", "categories", "conditions",
               "to_clear", "audit_ref", "inherit"}
EVIDENCE_KEYS = {"level", "refs", "checked", "note"}
LEVELS = {"fetched", "search", "blocked", "none"}
FLAGS = ("free", "paid", "licence_grant")
EXPR = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>|https?://|\bwww\.[a-z0-9-]+\.[a-z]")
TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
WITHHELD_NOTE = "withheld: no source allowed in this tier supports this value (data/source-policy.yaml)"
EXPR_NOTE = "withheld: source text, not a fact (expression guard)"


def default_path():
    if os.environ.get("SPECSHEET_SOURCE_POLICY"):
        return Path(os.environ["SPECSHEET_SOURCE_POLICY"])
    root = os.environ.get("SPECSHEET_ROOT")
    if root and (Path(root) / "data" / "source-policy.yaml").exists():
        return Path(root) / "data" / "source-policy.yaml"
    return CODE / "data" / "source-policy.yaml"


def host_of(url):
    """Hostname of a source URL: lowercased, trailing dot and port stripped; userinfo never counts (urllib .hostname)."""
    try:
        h = urllib.parse.urlsplit(str(url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return h.lower().rstrip(".")


DOC_URL = re.compile(r"\.(?:pdf|docx?|xlsx?|zip|png|jpe?g|webp)$|documentrequesthandler", re.I)


def is_document_url(url):
    """A URL that is itself a document (file), never a page: it cannot be an inheritance endpoint for a document_host document."""
    try:
        path = urllib.parse.urlsplit(str(url or "")).path
    except ValueError:
        return True
    return bool(DOC_URL.search(path))


def is_expression(v):
    if isinstance(v, str):
        return bool(EXPR.search(v))
    if isinstance(v, list):
        return any(is_expression(x) for x in v)
    if isinstance(v, dict):
        return any(is_expression(x) for x in v.values())
    return False


def _canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


ANY = object()


class PolicyError(SystemExit):
    pass


def validate(doc):
    """-> list of problems (empty = valid)."""
    bad = []
    if not isinstance(doc, dict):
        return ["policy is not a mapping"]
    bad += [f"unknown top-level key {k!r}" for k in sorted(set(doc) - TOP_KEYS)]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", str(doc.get("policy_version") or "")):
        bad.append("policy_version must be date.N")
    d = doc.get("defaults") or {}
    bad += [f"defaults: unknown key {k!r}" for k in sorted(set(d) - DEFAULT_KEYS)]
    un = d.get("unlisted") or {}
    bad += [f"defaults.unlisted: unknown key {k!r}" for k in sorted(set(un) - set(FLAGS))]
    if set(un) != set(FLAGS) or not all(isinstance(un[f], bool) for f in FLAGS if f in un):
        bad.append("defaults.unlisted needs boolean free, paid, licence_grant")
    elif un["paid"] or un["licence_grant"]:
        bad.append("defaults.unlisted: paid/licence_grant need fetched evidence, an unlisted domain has none")
    rr = doc.get("record_rules") or {}
    bad += [f"record_rules: unknown key {k!r}" for k in sorted(set(rr) - RULE_KEYS)]
    seen = {}
    for i, s in enumerate(doc.get("sources") or []):
        dom = str(s.get("domain") or "").lower().rstrip(".")
        tag = f"sources[{i}] {dom or '?'}"
        bad += [f"{tag}: unknown key {k!r}" for k in sorted(set(s) - SOURCE_KEYS)]
        if not dom or "/" in dom or ":" in dom:
            bad.append(f"{tag}: domain must be a bare hostname")
        if dom in seen:
            bad.append(f"{tag}: duplicate domain (also sources[{seen[dom]}])")
        seen.setdefault(dom, i)
        if s.get("match", "exact") not in ("exact", "subdomains"):
            bad.append(f"{tag}: match must be exact|subdomains")
        if not all(isinstance(s.get(f), bool) for f in FLAGS):
            bad.append(f"{tag}: free, paid and licence_grant must all be true|false")
            continue
        if s["licence_grant"] and not s["free"]:
            bad.append(f"{tag}: licence_grant without free")
        if s["paid"] and not s["licence_grant"]:
            bad.append(f"{tag}: paid without licence_grant")
        ev = s.get("evidence") or {}
        if not isinstance(ev, dict):
            bad.append(f"{tag}: evidence must be a mapping"); continue
        bad += [f"{tag}: evidence: unknown key {k!r}" for k in sorted(set(ev) - EVIDENCE_KEYS)]
        if ev.get("level") not in LEVELS:
            bad.append(f"{tag}: evidence.level must be one of {sorted(LEVELS)}")
        if (s["paid"] or s["licence_grant"]) and (ev.get("level") != "fetched" or not ev.get("refs")):
            bad.append(f"{tag}: paid/licence_grant requires evidence.level fetched with refs")
        if s.get("kind") == "document_host" or s.get("inherit") is not None:
            if s.get("kind") != "document_host" or s.get("inherit") != "linking_page":
                bad.append(f"{tag}: a document host needs kind: document_host AND inherit: linking_page")
            if s["free"] or s["paid"] or s["licence_grant"]:
                bad.append(f"{tag}: document_host flags are the fallback for a document with no linking page and must all be false")
            if s.get("withhold_keys"):
                bad.append(f"{tag}: document_host takes the linking page's withhold_keys, not its own")
        wk = s.get("withhold_keys")
        if wk is not None and not (isinstance(wk, list) and all(isinstance(x, str) for x in wk)):
            bad.append(f"{tag}: withhold_keys must be a list of spec keys")
    return bad


class Policy:
    def __init__(self, doc, raw: bytes, path):
        self.doc, self.path = doc, str(path)
        self.version = doc["policy_version"]
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.unlisted_default = dict(doc["defaults"]["unlisted"])
        self.fail_on_unlisted = bool(doc["defaults"].get("fail_release_on_unlisted", True))
        rr = doc.get("record_rules") or {}
        self.drop_fields = list(rr.get("drop_record_fields") or [])
        self.exclude_demo = bool(rr.get("exclude_demo_records", True))
        self.exclude_categories = set(rr.get("exclude_categories") or [])
        self.withheld_status = rr.get("withheld_status") or "not_published"
        self.exact, self.subs = {}, {}
        for s in doc.get("sources") or []:
            (self.subs if s.get("match") == "subdomains" else self.exact)[s["domain"].lower().rstrip(".")] = s
        self._cache = {}
        self.unlisted = defaultdict(Counter)      # host -> {values, sources, documents} cited in what was published

    # ---- dispositions
    def entry(self, host):
        if host in self.exact:
            return self.exact[host]
        parts = host.split(".")
        for i in range(len(parts)):
            s = self.subs.get(".".join(parts[i:]))
            if s is not None:
                return s
        return None

    @staticmethod
    def split_ref(ref):
        """A source reference is a URL, or {url, linked_from} for a document found on a maker page (document_host inheritance)."""
        if isinstance(ref, dict):
            return ref.get("url"), ref.get("linked_from")
        return ref, None

    def disposition(self, url, linked_from=None):
        """Per-host disposition. A host listed as `kind: document_host, inherit: linking_page` (shared CDNs: cdn.shopify.com serves many
        makers) has no disposition of its own: the document gets the disposition of the page that linked it (its domain), so a maker's
        manual on a shared CDN is exactly as publishable as that maker's page. Without a linking page it falls back to the host's own
        (all-false) flags. No inheritance chains, independent of how the linking host is classified (review 6 fix 3): the linking page
        must be a listed `kind: maker` host other than the document's own host, and must not itself be a document URL (a PDF, a document
        handler); any other edge (another document host, a retail/unlisted host, a document on a maker host) is ineligible and the
        document keeps the all-false fallback."""
        url, lf = self.split_ref(url)
        linked_from = linked_from or lf
        h = host_of(url)
        s = self.entry(h) if h else None
        if s is not None and s.get("kind") == "document_host" and linked_from:
            ph = host_of(linked_from)
            ps = self.entry(ph) if ph else None
            if ps is not None and ps.get("kind") == "maker" and ph != h and not is_document_url(linked_from):
                ck = (h, ph)
                d = self._cache.get(ck)
                if d is None:
                    base = self.disposition(linked_from)
                    d = dict(base, host=h, domain=s["domain"], listed=base["listed"], inherited_from=base["host"])
                    self._cache[ck] = d
                return d
        d = self._cache.get(h)
        if d is None:
            base = s if s is not None else self.unlisted_default
            d = {"free": base["free"], "paid": base["paid"], "licence_grant": base["licence_grant"],
                 "withhold_keys": list((s or {}).get("withhold_keys") or []), "domain": s["domain"] if s else None, "listed": s is not None,
                 "host": h}
            self._cache[h] = d
        return d

    def allowed(self, url, tier, key=None, linked_from=None):
        d = self.disposition(url, linked_from)
        return bool(d[tier]) and (key is None or key not in d["withhold_keys"])

    def note_unlisted(self, url, what, n=1):
        d = self.disposition(url)
        if not d["listed"] and not d.get("inherited_from"):
            self.unlisted[d["host"] or "(no host)"][what] += n

    # ---- values
    def _withheld(self, sp, note=WITHHELD_NOTE):
        return {"value": None, "unit": sp.get("unit"), "status": self.withheld_status, "sources": [], "claims": [], "kind": None,
                "confidence": None, "source_scope": "none", "note": note}

    def gate_spec(self, key, sp, tier, url_of, support=None):
        """sp: resolved spec (record.schema.json $defs.resolved). url_of(sid) -> url | None. support(sid, value|ANY, claim_ids) -> bool.
        Returns (spec, withheld)."""
        if sp.get("status") == self.withheld_status and not sp.get("sources"):
            return sp, False
        if is_expression(sp.get("value")):
            return self._withheld(sp, EXPR_NOTE), True

        def keep(sids, value, claims):
            out = []
            for s in sids or []:
                u = url_of(s)
                if u is None or not self.allowed(u, tier, key):
                    continue
                if support is not None and claims and not support(s, value, claims):
                    continue
                out.append(s)
            return out

        def gate_alts(alts):
            res = []
            for a in alts or []:
                ks = keep(a.get("sources"), a.get("value"), a.get("claims"))
                if ks:
                    res.append(dict(a, sources=ks))
            return res

        st = sp.get("status")
        out = dict(sp)
        if sp.get("conditional"):
            rows = []
            for r in sp["conditional"]:
                if is_expression(r.get("value")):
                    continue
                ks = keep(r.get("sources"), r.get("value") if r.get("status") == "known" else ANY, r.get("claims"))
                if not ks:
                    continue
                nr = dict(r, sources=ks)
                if r.get("alternatives"):
                    alts = gate_alts(r["alternatives"])
                    if alts:
                        nr["alternatives"] = alts
                    else:
                        nr.pop("alternatives")
                rows.append(nr)
            if rows:
                out["conditional"] = rows
            else:
                out.pop("conditional")
        if sp.get("alternatives"):
            alts = gate_alts(sp["alternatives"])
            if alts:
                out["alternatives"] = alts
            else:
                out.pop("alternatives")
        if st == "known":
            ks = keep(sp.get("sources"), sp.get("value"), sp.get("claims"))
            if not ks:
                return self._withheld(sp), True
            out["sources"] = ks
            if str(sp.get("note") or "").startswith("merged:") and set(ks) != set(sp.get("sources") or []):
                return self._withheld(sp), True     # a merged item list holds facts from every source: all of them must be allowed
        elif st == "conflicted":
            frames = Counter(_canon([a.get("kind"), a.get("basis"), a.get("measurement_mode")]) for a in out.get("alternatives") or [])
            if not frames or max(frames.values()) < 2:
                return self._withheld(sp), True     # the disagreement is gone once dropped sources are removed: never imply one
            out["sources"] = sorted({s for a in out["alternatives"] for s in a["sources"]})
        elif sp.get("conditional") or sp.get("alternatives"):
            if not out.get("conditional") and not out.get("alternatives"):
                return self._withheld(sp), True
            out["sources"] = sorted({s for r in out.get("conditional") or [] for s in r["sources"]} |
                                    {s for a in out.get("alternatives") or [] for s in a["sources"]})
        else:
            ks = keep(sp.get("sources"), ANY, sp.get("claims"))
            if sp.get("sources") and not ks:
                return self._withheld(sp), True
            out["sources"] = ks
        return out, False

    def gate_specs(self, specs, tier, url_of, support=None):
        """{key: spec} -> ({key: spec}, withheld_keys). url_of/support as gate_spec but called with (key, sid)."""
        out, wk = {}, []
        for k, sp in specs.items():
            g, w = self.gate_spec(k, sp, tier, lambda s, k=k: url_of(k, s), (lambda s, v, c, k=k: support(k, s, v, c)) if support else None)
            out[k] = g
            if w:
                wk.append(k)
        return out, wk

    def source_entries(self, sources, tier):
        """Source table of a published record/revision -> only the tier's sources, each with licence_grant."""
        return [dict(s, licence_grant=bool(self.disposition(s.get("url"), s.get("linked_from"))["licence_grant"])) for s in sources or []
                if self.allowed(s.get("url"), tier, linked_from=s.get("linked_from"))]

    def documents(self, docs, tier):
        """Document links of a record, one entry per linking edge {url, linked_from}: a document on a document_host inherits from its OWN
        edge's linking page only (review 6 fix 3: never from the record's first source); an entry without linked_from keeps the host's
        all-false fallback."""
        return [d for d in docs or [] if self.allowed(d.get("url"), tier, linked_from=d.get("linked_from"))]

    def page_url(self, sources):
        """The record's own page: first source that is neither inherited (via) nor a document (linked_from) nor on a document host."""
        for s in sources or []:
            e = self.entry(host_of(s.get("url")))
            if not s.get("via") and not s.get("linked_from") and not (e and e.get("kind") == "document_host"):
                return s.get("url")
        return None

    def identity_ok(self, own_urls, tier):
        own = list(own_urls)
        return not own or any(self.allowed(u, tier) for u in own)

    def note_published(self, rec):
        """Count unlisted domains cited by a published (gated) record: values, record sources, documents."""
        by = {s["id"]: {"url": s.get("url"), "linked_from": s.get("linked_from")} for s in rec.get("sources") or []}
        for s in rec.get("sources") or []:
            self.note_unlisted({"url": s.get("url"), "linked_from": s.get("linked_from")}, "sources")
        for d in rec.get("documents") or []:
            self.note_unlisted({"url": d.get("url"), "linked_from": d.get("linked_from")}, "documents")
        for sp in (rec.get("specs") or {}).values():
            for sid in {x for x in sp.get("sources") or []}:
                if sid in by:
                    self.note_unlisted(by[sid], "values")

    def gate(self, record, tier, support=None):
        """Published record (docs/api/v1/<cat>/products/<id>.json shape) -> gated copy, or None if the tier omits it."""
        assert tier in TIERS, tier
        if (self.exclude_demo and record.get("demo")) or record.get("category") in self.exclude_categories:
            return None
        srcs = record.get("sources") or []
        if not self.identity_ok(({"url": s.get("url"), "linked_from": s.get("linked_from")} for s in srcs if not s.get("via")), tier):
            return None
        rec = copy.deepcopy(record)
        for f in self.drop_fields:
            rec.pop(f, None)
        url = {s["id"]: ({"url": s.get("url"), "linked_from": s["linked_from"]} if s.get("linked_from") else s.get("url")) for s in srcs}
        sup = (lambda k, s, v, c: support(record["id"], k, url.get(s), v, c)) if support else None
        rec["specs"], _ = self.gate_specs(rec.get("specs") or {}, tier, lambda k, s: url.get(s), sup)
        rec["sources"] = self.source_entries(srcs, tier)
        if "documents" in rec:
            rec["documents"] = self.documents(rec["documents"], tier)
        for fld in ("name", "variant_label", "variant", "family"):
            if isinstance(rec.get(fld), str):
                rec[fld] = TAG.sub("", rec[fld]).strip()
        for rv in rec.get("revisions") or []:
            ru = {s["id"]: s.get("url") for s in rv.get("sources") or []}
            rv["specs"], _ = self.gate_specs(rv.get("specs") or {}, tier, lambda k, s, ru=ru: ru.get(s))
            rv["specs"] = {k: v for k, v in rv["specs"].items() if v.get("status") != self.withheld_status or v.get("sources")}
            rv["sources"] = self.source_entries(rv.get("sources"), tier)
            rv["differs"] = [k for k in rv.get("differs") or [] if k in rv["specs"]]
        return rec

    # ---- outputs
    def granted_value(self, sp, by_id):
        return sp.get("status") == "known" and any(by_id.get(s, {}).get("licence_grant") for s in sp.get("sources") or [])

    def count(self, rec):
        """-> (known values, granted values) of a gated record."""
        by = {s["id"]: s for s in rec.get("sources") or []}
        known = granted = 0
        for sp in (rec.get("specs") or {}).values():
            if sp.get("status") == "known":
                known += 1
                granted += self.granted_value(sp, by)
        return known, granted

    def attribution(self, brand="specsheet"):
        lines = []
        for s in self.doc.get("sources") or []:
            if s.get("licence_grant"):
                line = next((c.split("'")[1] for c in s.get("conditions") or [] if c.startswith("Attribute: '") and c.count("'") >= 2), None)
                lines.append({"domain": s["domain"], "credit": s.get("credit"), "line": line or f"Source: {s.get('credit') or s['domain']}"})
        return {"dataset": f"Data: {brand} (ODbL), sources linked per value", "sources": lines}

    def manifest_block(self, brand="specsheet"):
        return dict({"policy_version": self.version, "policy_sha256": self.sha256}, **LICENSE, attribution=self.attribution(brand))

    def sources_doc(self):
        """docs/sources.json: generated from the policy, grouped granted / facts_only (free: false domains are never shown)."""
        g, f = [], []
        for s in self.doc.get("sources") or []:
            if not s.get("free"):
                continue
            e = {"domain": s["domain"], "match": s.get("match", "exact"), "kind": s.get("kind"), "credit": s.get("credit") or s["domain"]}
            if s.get("categories"):
                e["categories"] = s["categories"]
            if s.get("licence_grant"):
                e["attribution"] = self.attribution()["sources"][len(g)]["line"]
                e["conditions"] = s.get("conditions") or []
                e["paid"] = bool(s.get("paid"))
                g.append(e)
            else:
                if s.get("to_clear"):
                    e["to_clear"] = s["to_clear"]
                f.append(e)
        return {"generated_from": "data/source-policy.yaml", "policy_version": self.version, "policy_sha256": self.sha256,
                "license_scope": LICENSE["license_scope"], "granted": g, "facts_only": f}

    def unlisted_report(self):
        return {h: dict(c) for h, c in sorted(self.unlisted.items())}

    def check_unlisted(self, release=None, out=sys.stderr, what="build"):
        """Print unlisted domains with counts; with RELEASE=1 exit non-zero naming those cited by a value or a record source."""
        release = os.environ.get("RELEASE") == "1" if release is None else release
        rep = self.unlisted_report()
        for h, c in rep.items():
            print(f"source-policy: unlisted domain {h}: " + ", ".join(f"{n} {k}" for k, n in sorted(c.items())), file=out)
        blocking = sorted(h for h, c in rep.items() if c.get("values") or c.get("sources"))
        if release and self.fail_on_unlisted and blocking:
            raise SystemExit(f"{what}: RELEASE=1 and published values cite domains not in data/source-policy.yaml: {', '.join(blocking)} "
                             "(give each an explicit disposition, A5)")
        return blocking


def load(path=None):
    p = Path(path) if path else default_path()
    raw = p.read_bytes()
    doc = yaml.safe_load(raw)
    bad = validate(doc)
    if bad:
        raise PolicyError(f"{p}: invalid source policy: " + "; ".join(bad))
    return Policy(doc, raw, p)


def coverage_table(per_cat):
    """per_cat: {cat: {"free": [records, values], "granted": [...], "paid": [...]}} -> coverage.json body with totals."""
    tot = {t: {"records": 0, "values": 0} for t in ("free", "granted", "paid")}
    cats = {}
    for c in sorted(per_cat):
        cats[c] = {t: {"records": per_cat[c][t][0], "values": per_cat[c][t][1]} for t in ("free", "granted", "paid")}
        for t in tot:
            tot[t]["records"] += per_cat[c][t][0]; tot[t]["values"] += per_cat[c][t][1]
    return {"definition": "records = published record files; values = known spec values. free = shown on the free tier (facts with links); "
                          "granted = free values with at least one licence_grant:true source (under our ODbL grant); paid = paid-tier values",
            "categories": cats, "total": tot}


if __name__ == "__main__":
    pol = load()
    if len(sys.argv) > 2 and sys.argv[1] == "unlisted":
        import glob
        for f in glob.glob(os.path.join(sys.argv[2], "*", "products", "*.json")):
            pol.note_published(json.load(open(f)))
        pol.check_unlisted(release=False, out=sys.stdout)
    print(f"{pol.path}: valid, policy_version {pol.version}, sha256 {pol.sha256[:12]}, {len(pol.exact) + len(pol.subs)} domains")
