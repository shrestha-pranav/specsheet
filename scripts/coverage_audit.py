#!/usr/bin/env python3
"""Coverage audit: per category and spec key, how full are we, and how much evidence do we already hold but have not read?

    python3 -I scripts/coverage_audit.py [--db state/specsheet.sqlite] [--before OLD.sqlite] [--md team/queue/coverage-audit.md] [--json OUT]

Fill rate (per category, per profile key): share of in-scope entities (kind model/configuration/package with at least one accepted claim,
i.e. rows of the trusted dataset) that have an ACCEPTED known claim for the key (`trusted`), and the same counting candidates too
(`preview`). Item keys also report per-field fill (out.ports.pps = share of entities whose accepted port rows state a PPS range on at least
one port). --before adds the same numbers for an older store (what a round changed).

Evidence on hand but unparsed (per category):
  documents_linked / documents_skipped / documents_not_fetched / documents_fetched_not_parsed (no document parser for the category, or no
  text) / documents_parsed / documents_attached   (raw/_documents: crawler/documents.py + scripts/docattach.py)
  unmapped_labels      distinct source labels the adapters saw but did not map (import `unmapped` table), with occurrences
  image_only_specs     product-gallery images whose file name says spec/parameter/label (raw/*/products/*/assets.json), not OCR'd
Nothing here writes outside the --md / --json outputs; it is read-only over state/ and raw/.
"""
import argparse, collections, json, re, sqlite3, sys
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "crawler"), str(CODE / "crawler" / "adapters")]
import catmeta  # noqa: E402
import docattach as DA  # noqa: E402

ROOT = catmeta.ROOT
SPEC_IMG = re.compile(r"spec|param|label|rating|dimension|size[-_]chart|_td\d|detail[-_]?page", re.I)
FOCUS = [("chargers", "pd.pps"), ("chargers", "out.ports.pps"), ("chargers", "out.ports.fixed_pdos"), ("chargers", "pd.pps_max_voltage"),
         ("chargers", "pd.max_fixed_voltage"), ("power-banks", "pd.pps"), ("power-banks", "out.ports.pps"), ("power-banks", "out.ports.fixed_pdos"),
         ("monitors", "flk.pwm"), ("monitors", "usb.usbc_pd_w"), ("ssds", "hw.dram_type"), ("laptops", "mem.size"), ("tvs", "hdmi.has_4k120"),
         ("routers", "wifi.band_count")]


def fill(db):
    con = sqlite3.connect(db)
    ents = collections.defaultdict(set)
    for cat, eid in con.execute("SELECT e.category, e.id FROM entities e WHERE e.kind IN ('model','configuration','package') AND "
                                "EXISTS (SELECT 1 FROM claims c WHERE c.entity_id=e.id AND c.review='accepted')"):
        ents[cat].add(eid)
    have = collections.defaultdict(lambda: collections.defaultdict(lambda: {"trusted": set(), "preview": set()}))
    for cat, eid, key, review, val in con.execute(
            "SELECT e.category, c.entity_id, c.mapped_key, c.review, c.norm_value FROM claims c JOIN entities e ON e.id=c.entity_id "
            "WHERE c.status='known' AND c.mapped_key IS NOT NULL AND c.review IN ('accepted','candidate')"):
        if eid not in ents[cat]:
            continue
        scopes = ("trusted", "preview") if review == "accepted" else ("preview",)
        for sc in scopes:
            have[cat][key][sc].add(eid)
        try:
            v = json.loads(val) if val else None
        except ValueError:
            v = None
        if isinstance(v, list) and v and all(isinstance(r, dict) for r in v):
            for f in {f for r in v for f, x in r.items() if x not in (None, "", [])}:
                for sc in scopes:
                    have[cat][f"{key}.{f}"][sc].add(eid)
    out = {}
    for cat, es in ents.items():
        n = len(es)
        out[cat] = {"entities": n, "keys": {k: {"trusted": round(len(v["trusted"]) / n, 4), "preview": round(len(v["preview"]) / n, 4),
                                                "n_trusted": len(v["trusted"])} for k, v in sorted(have[cat].items())}}
    for cat, cfg in _profiles().items():
        if cat in out:
            for k in cfg:
                out[cat]["keys"].setdefault(k, {"trusted": 0.0, "preview": 0.0, "n_trusted": 0})
    return out


def _profiles():
    import yaml
    out = {}
    for p in sorted((ROOT / "research").glob("*/spec-profile.yaml")):
        try:
            out[p.parent.name] = [s["key"] for s in yaml.safe_load(p.read_text())["specs"]]
        except Exception:  # noqa
            continue
    return out


def evidence(db, attach_stats=None):
    d = ROOT / "raw" / "_documents"
    disc = json.loads((d / "discovery.json").read_text())["docs"] if (d / "discovery.json").exists() else []
    snaps = {}
    if (d / "snapshots.jsonl").exists():
        for l in (d / "snapshots.jsonl").read_text().splitlines():
            r = json.loads(l)
            snaps.setdefault(r["ref"], []).append(r)
    ev = collections.defaultdict(collections.Counter)
    for x in disc:
        for cat in x["categories"] or ["(unbound)"]:
            c = ev[cat]
            c["documents_linked"] += 1
            if x["decision"] != "fetch":
                c["documents_skipped"] += 1
                continue
            ok = [r for r in snaps.get(x["norm_url"], []) if r.get("status") == 200 and r.get("blob")]
            if not ok:
                c["documents_not_fetched" if not snaps.get(x["norm_url"]) else "documents_fetch_failed"] += 1
                continue
            has_text = (d / "text" / f"{ok[-1]['snapshot'].split(':', 1)[1]}.json").exists()
            if cat in DA.CATEGORIES and has_text:
                c["documents_parsed"] += 1
            else:
                c["documents_fetched_not_parsed"] += 1
    con = sqlite3.connect(db)
    for cat, n, occ in con.execute("SELECT category, COUNT(*), SUM(n) FROM unmapped WHERE what='source_label_not_mapped_by_adapter' GROUP BY category"):
        ev[cat]["unmapped_labels"] = n; ev[cat]["unmapped_label_occurrences"] = occ or 0
    for cat, n in con.execute("SELECT e.category, COUNT(DISTINCT i.entity_id) FROM identity_events i JOIN entities e ON e.id=i.entity_id "
                              "WHERE i.event='document_attach' GROUP BY e.category"):
        ev[cat]["documents_attached_entities"] = n
    for cat, n in con.execute("SELECT category, COUNT(*) FROM identity_events WHERE event='document_proposal' GROUP BY category"):
        ev[cat]["document_proposals"] = n
    imgs = collections.Counter()
    for f in (ROOT / "raw").glob("*/products/*/assets.json"):
        try:
            for im in json.loads(f.read_text()).get("images") or []:
                u = im.get("url") if isinstance(im, dict) else im
                if u and SPEC_IMG.search(u.rsplit("/", 1)[-1]):
                    imgs[f.parts[-4]] += 1
        except ValueError:
            continue
    return {k: dict(v) for k, v in sorted(ev.items())}, dict(imgs)


def md(after, before, ev, imgs):
    L = ["# Coverage audit (scripts/coverage_audit.py)", "",
         "Fill = share of trusted rows (entities with >=1 accepted claim) holding an accepted known value; preview counts candidates too.",
         "Item fields (`out.ports.pps`) = at least one port row states the field. Regenerate: `python3 -I scripts/coverage_audit.py --md team/queue/coverage-audit.md`.", "",
         "## Focus keys (presets + demand survey)", "", "| category | key | trusted | preview | " + ("before (trusted) |" if before else ""),
         "|---|---|---|---|" + ("---|" if before else "")]
    for cat, key in FOCUS:
        a = (after.get(cat) or {}).get("keys", {}).get(key)
        if a is None:
            continue
        b = (before or {}).get(cat, {}).get("keys", {}).get(key) if before else None
        L.append(f"| {cat} | {key} | {a['trusted']:.1%} ({a['n_trusted']}) | {a['preview']:.1%} | " + (f"{b['trusted']:.1%} ({b['n_trusted']}) |" if b else ("- |" if before else "")))
    L += ["", "## Evidence on hand but unparsed", "", "| category | docs linked | skipped | not fetched | fetched, no parser/text | parsed | entities w/ doc | proposals | unmapped labels (occ.) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for cat, c in ev.items():
        L.append(f"| {cat} | {c.get('documents_linked', 0)} | {c.get('documents_skipped', 0)} | {c.get('documents_not_fetched', 0) + c.get('documents_fetch_failed', 0)} | "
                 f"{c.get('documents_fetched_not_parsed', 0)} | {c.get('documents_parsed', 0)} | {c.get('documents_attached_entities', 0)} | {c.get('document_proposals', 0)} | "
                 f"{c.get('unmapped_labels', 0)} ({c.get('unmapped_label_occurrences', 0)}) |")
    L += ["", "Image-only spec candidates (gallery images named spec/param/label, never OCR'd), by crawl.py v0 store: " +
          (", ".join(f"{k} {v}" for k, v in sorted(imgs.items(), key=lambda kv: -kv[1])) or "none"), "",
          "## Lowest-filled core keys per category (trusted)", ""]
    prof = _profiles()
    import yaml
    for cat in sorted(after):
        p = CODE / "research" / cat / "spec-profile.yaml"
        core = [s["key"] for s in yaml.safe_load(p.read_text())["specs"] if s.get("tier") == "core"] if p.exists() else []
        ks = sorted((after[cat]["keys"].get(k, {"trusted": 0})["trusted"], k) for k in core if k in prof.get(cat, []))
        L.append(f"- **{cat}** ({after[cat]['entities']} rows): " + ", ".join(f"{k} {v:.0%}" for v, k in ks[:8]))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "state" / "specsheet.sqlite"))
    ap.add_argument("--before")
    ap.add_argument("--md")
    ap.add_argument("--json")
    a = ap.parse_args()
    after = fill(a.db)
    before = fill(a.before) if a.before else None
    ev, imgs = evidence(a.db)
    if a.md:
        Path(a.md).write_text(md(after, before, ev, imgs))
    res = {"fill": after, "before": before, "evidence": ev, "image_only_specs": imgs}
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, sort_keys=True))
    for cat, key in FOCUS:
        x = (after.get(cat) or {}).get("keys", {}).get(key)
        b = (before or {}).get(cat, {}).get("keys", {}).get(key) if before else None
        if x:
            print(f"{cat:12s} {key:24s} trusted {x['trusted']:.1%} preview {x['preview']:.1%}" + (f"  (before {b['trusted']:.1%})" if b else ""))


if __name__ == "__main__":
    main()
