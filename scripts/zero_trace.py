#!/usr/bin/env python3
"""Zero-trace check for `free: false` sources (A3-fix, Codex review-10 item 4). Read-only; exit 1 on any trace.

A host the source policy lists with free: false (data/source-policy.yaml; excluded, retail, AOC takedown ...) must leave NO trace in what we
serve for free: the static site + dataset (docs/, incl. docs/api/v1 trusted AND preview files, the lookup / alias search index, sitemap,
llms.txt, sources.json), and the Worker pack (api-worker/pack: records, index, bulk, match catalogue, presets) that /v1 query and the MCP tools
read. Three checks over every text file there (json / jsonl / .gz / txt / xml / html / js / css / md):

  url    no URL whose policy entry is free: false (path_prefix entries by path; document_host entries are skipped: their disposition is
         inherited from the linking page, checked by the gate itself), and no bare domain token of such a host (exact / subdomains entries);
  label  no `credit` label of a free: false entry;
  value  from the store (state/specsheet.sqlite): a value that ONLY free: false sources support (accepted or candidate known claims, as
         preview publishes candidates; no free source
         states the same normalised value for that entity + key) appears nowhere as a published value, preview value, or alternative
         (product records, pack records, bulk rows, index rows). Images / documents / media are covered by the url check.

  python3 -I scripts/zero_trace.py [--db state/specsheet.sqlite] [--root .] [--json]
"""
import argparse, gzip, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE / "scripts"))
import source_policy  # noqa: E402

TEXT = {".json", ".jsonl", ".txt", ".xml", ".html", ".js", ".mjs", ".css", ".md", ".csv", ".gz"}
URL = re.compile(r"https?://[^\s\"'<>\\)\]},]+", re.I)


def canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read(p):
    try:
        if p.suffix == ".gz":
            with gzip.open(p, "rt", encoding="utf-8", errors="replace") as f:
                return f.read()
        return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, EOFError):
        return ""


def nonfree_entries(pol):
    return [s for s in pol.doc.get("sources") or [] if s.get("free") is False and s.get("kind") != "document_host"]


def nonfree_url(pol, url):
    s = pol.entry_for(url)
    return s is not None and s.get("free") is False and s.get("kind") != "document_host"


def domain_regex(entries):
    doms = sorted({s["domain"].lower().rstrip(".") for s in entries if s.get("match") in ("exact", "subdomains")}, key=len, reverse=True)
    if not doms:
        return None
    return re.compile(r"(?<![\w.-])(?:[\w-]+\.)*(?:" + "|".join(re.escape(d) for d in doms) + r")(?![\w-])", re.I)


def tainted_values(db, pol):
    """-> {(entity_id, key): {canon(value)}} supported only by free: false sources."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    url = {(e, s): u for e, s, u in con.execute("SELECT entity_id, sid, url FROM entity_sources")}
    lf = {(e, s): l for e, s, l in con.execute("SELECT entity_id, sid, linked_from FROM source_links")}
    free, nonfree = defaultdict(set), defaultdict(set)
    for eid, key, sid, ok, nv, v in con.execute("SELECT entity_id, mapped_key, source, norm_ok, norm_value, value FROM claims "
                                                "WHERE review IN ('accepted', 'candidate') AND status='known' AND mapped_key IS NOT NULL"):
        u = url.get((eid, sid))
        if u is None:
            continue
        try:
            val = canon(json.loads(nv if ok else v))
        except (TypeError, ValueError):
            continue
        (free if pol.disposition(u, lf.get((eid, sid)))["free"] else nonfree)[(eid, key)].add(val)
    con.close()
    return {k: vs - free.get(k, set()) for k, vs in nonfree.items() if vs - free.get(k, set())}


def record_values(rec):
    for k, sp in (rec.get("specs") or {}).items():
        if isinstance(sp, dict):
            if sp.get("value") is not None:
                yield k, sp["value"], "value"
            for a in sp.get("alternatives") or []:
                if isinstance(a, dict) and a.get("value") is not None:
                    yield k, a["value"], "alternative"


def scan_records(p, txt, tainted, hits):
    def check(eid, k, v, where):
        if canon(v) in tainted.get((eid, k), ()):
            hits.append({"check": "value", "file": str(p), "entity": eid, "key": k, "where": where, "value": v})

    def walk(obj):
        if isinstance(obj, dict):
            if "id" in obj and isinstance(obj.get("specs"), dict):
                for k, v, where in record_values(obj):
                    check(obj["id"], k, v, where)
            elif "id" in obj and isinstance(obj.get("v"), dict):         # index rows: v = headline values, x = alternatives
                for k, v in obj["v"].items():
                    if v is not None:
                        check(obj["id"], k, v, "index")
                for k, alts in (obj.get("x") or {}).items() if isinstance(obj.get("x"), dict) else ():
                    for a in alts if isinstance(alts, list) else [alts]:
                        check(obj["id"], k, a.get("v") if isinstance(a, dict) else a, "index-alternative")
            else:
                for x in obj.values():
                    if isinstance(x, (dict, list)):
                        walk(x)
        elif isinstance(obj, list):
            for x in obj:
                if isinstance(x, (dict, list)):
                    walk(x)

    docs = []
    if p.name.endswith(".jsonl") or p.name.endswith(".jsonl.gz"):
        for line in txt.splitlines():
            try:
                docs.append(json.loads(line))
            except ValueError:
                pass
    else:
        try:
            docs.append(json.loads(txt))
        except ValueError:
            return
    for d in docs:
        walk(d)


def run(root, db, pol=None):
    pol = pol or source_policy.load()
    entries = nonfree_entries(pol)
    dom = domain_regex(entries)
    labels = sorted({s["credit"] for s in entries if s.get("credit")}, key=len, reverse=True)
    tainted = tainted_values(db, pol) if Path(db).exists() else {}
    hits, files = [], 0
    for base in (root / "docs", root / "api-worker" / "pack"):
        for p in sorted(base.rglob("*")):
            if not p.is_file() or (p.suffix not in TEXT):
                continue
            txt = read(p)
            files += 1
            for u in set(URL.findall(txt)):
                if nonfree_url(pol, u):
                    hits.append({"check": "url", "file": str(p), "url": u})
            if dom:
                for m in set(x.group(0) for x in dom.finditer(txt)):
                    hits.append({"check": "url", "file": str(p), "domain": m})
            for lab in labels:
                if lab in txt:
                    hits.append({"check": "label", "file": str(p), "label": lab})
            if tainted and (p.suffix == ".json" or p.name.endswith(".jsonl.gz") or p.name.endswith(".jsonl")):
                scan_records(p, txt, tainted, hits)
    return {"files": files, "nonfree_hosts": len(entries), "tainted_values": sum(len(v) for v in tainted.values()),
            "tainted_entities": len({e for e, _ in tainted}), "hits": hits}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(CODE))
    ap.add_argument("--db", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    r = run(root, a.db or root / "state" / "specsheet.sqlite")
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    else:
        print(f"zero-trace: {r['files']} files, {r['nonfree_hosts']} free:false hosts, {r['tainted_values']} values only they support "
              f"({r['tainted_entities']} entities): {len(r['hits'])} trace(s)")
        for h in r["hits"][:50]:
            print("  " + json.dumps(h, ensure_ascii=False))
    sys.exit(1 if r["hits"] else 0)


if __name__ == "__main__":
    main()
