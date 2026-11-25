#!/usr/bin/env python3
"""Owner/maintainer review of corrections (D9.2): show the evidence, ask the reviewer, append the decision to data/decisions/ledger.jsonl.

  python3 -I scripts/review_corrections.py [--by HANDLE] [REF ...]      interactive review of undecided claims (all, or the refs: 12, a3)
  python3 -I scripts/review_corrections.py --revert CLAIM_ID [--by HANDLE]   a later reject_claim line (one line reverts an accept)
  python3 -I scripts/review_corrections.py --seed team/queue/ssd-dram-seed.md   print prefilled issue-form links for family facts (posts nothing)

A PERSON runs this at a terminal: it refuses to run without a TTY and refuses agent-looking handles, and it writes only what the reviewer
typed (handle, decision, reason, transcription). There is no LLM decision. Each claim c_corr_<ref>_<n> gets its own line
  {"id": "d_corr_<ref>_<n>", "at": ISO, "by": "<handle>", "action": "accept_claim|reject_claim", "claim": "c_corr_<ref>_<n>",
   "reason": "...", "evidence": "<issue url>"}
A photo's transcription (<= 125 chars: the model number and the fact as printed) is written back into the claim file before an accept.
After deciding: rebuild (import.py), then close each issue with a link to the release (team/queue/corrections.md lists the drafts).
"""
import argparse, datetime as dt, json, os, re, sys, urllib.parse
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corrections as CR  # noqa: E402
import decisions as D  # noqa: E402
import source_policy as SP  # noqa: E402

ROOT = CR.ROOT


def ledger_path(data_dir=None):
    return Path(data_dir or ROOT / "data") / "decisions" / "ledger.jsonl"


def valid_handle(h):
    h = (h or "").strip()
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,38}", h)) and not D.AGENT_BY.search(h)


def decision_line(cid, action, by, reason, evidence, at=None, data_dir=None):
    """-> the ledger dict for one claim (id d_corr_<ref>_<n>, suffixed _2, _3 ... for later decisions on the same claim)."""
    if action not in ("accept_claim", "reject_claim"):
        raise ValueError(action)
    if not valid_handle(by):
        raise SystemExit(f"{by!r} is not a reviewer handle (a person decides corrections; agents never write ledger lines)")
    if not str(reason or "").strip():
        raise SystemExit("a decision needs a reason")
    base = "d_" + cid[2:]
    used = set()
    lp = ledger_path(data_dir)
    if lp.exists():
        used = {json.loads(x).get("id") for x in lp.read_text().splitlines() if x.strip() and not x.lstrip().startswith("#")}
    did, k = base, 1
    while did in used:
        k += 1; did = f"{base}_{k}"
    line = {"id": did, "at": at or dt.datetime.now(dt.timezone.utc).strftime("%FT%TZ"), "by": by.strip(), "action": action, "claim": cid,
            "reason": str(reason).strip()[:300]}
    if evidence:
        line["evidence"] = evidence
    return line


def append(lines, data_dir=None):
    lp = ledger_path(data_dir)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("a") as f:
        for ln in lines:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")


def default_reason(doc):
    t = (doc.get("evidence") or {}).get("type")
    return {"E1": "E1 label photo, model visible", "E2": "E2 maker page names the model and states the value",
            "E3": "E3 measurement page names the model and states the value", "E4": "E4 contributor measurement, meter and model visible"}.get(t, "")


def show(doc, bad, cl, decided, pol, out=None):
    out = out or sys.stdout
    ev = doc.get("evidence") or {}
    p = lambda *a: print(*a, file=out)
    p("=" * 100)
    p(f"Correction {CR.ref_of(doc)}  {doc.get('url') or CR.pointer(doc)}  ({doc.get('state') or 'proposal'}, submitted {doc.get('submitted_at')}, by {doc.get('submitted_by')})")
    p(f"  terms acknowledged: {doc.get('terms_ack')}   conflict of interest: {doc.get('coi')}")
    for cid, eid in CR.claim_ids(doc):
        cat = cl.cat.get(eid)
        st, val = CR.current_value(cat, eid, doc.get("key"))
        name, ids = eid, []
        dp = ROOT / "docs" / "api" / "v1" / str(cat) / "products" / f"{eid}.json"
        if dp.exists():
            d = json.loads(dp.read_text())
            name = f"{d.get('brand', {}).get('name', '')} {d.get('name', '')}".strip()
            ids = [f"{i['scheme']}:{i['value']}" for i in d.get("identifiers") or [] if i.get("role") == "key"]
        p(f"  {cid}: {eid} [{cat}/{cl.kind.get(eid)}] {name}  identifiers: {', '.join(ids) or 'n/a'}  {'DECIDED: ' + decided[cid]['action'] + ' by ' + decided[cid]['by'] if cid in decided else ''}")
        p(f"      {doc.get('key')}: published {st}{'' if val is None else ' = ' + json.dumps(val)}")
    if doc.get("applies_to"):
        p(f"  family scope: {doc['entity']} -> {len(doc['applies_to'])} configurations listed")
    ok, nv = CR.normalised(cl.cat.get(CR.claim_ids(doc)[0][1]), doc.get("key"), doc.get("value"))
    p(f"  PROPOSED: {doc.get('value')!r} -> {json.dumps(nv) if ok else 'DOES NOT NORMALISE'}   kind {doc.get('kind')}"
      f"{'  mode ' + str((doc.get('measurement') or {}).get('mode')) if doc.get('measurement') else ''}")
    src = CR.source_of(doc, pol)
    p(f"  evidence {ev.get('type')}: source {src['tier']} {src['url']}")
    for u in [ev.get("url")] + list(ev.get("extra_urls") or []) + [ev.get("single_design_url")]:
        if u:
            d = pol.disposition(u)
            e = pol.entry_for(u) or {}
            p(f"    url {u}  [{e.get('kind') or 'unlisted'}, free {d['free']}, crawl {pol.crawl(u)}]")
    for n, im in enumerate(ev.get("images") or [], 1):
        p(f"    photo {n}: {im.get('sha256')}  transcription: {im.get('transcription') or '(none yet)'}   (open the issue to view it)")
    if doc.get("conditions_text"):
        p(f"  conditions (submitter): {doc['conditions_text']}")
    p("  check: " + ("ok" if not bad else "; ".join(f"{c}: {m}" for c, m in bad)))


def ask(prompt, default=""):
    v = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    return v or default


def yes(prompt):
    return ask(prompt + " (y/N)").lower() in ("y", "yes")


def review(refs, by, data_dir=None):
    pol = SP.load()
    cl = CR.Catalogue(data_dir)
    res = CR.check_all(data_dir, pol)
    decided = CR.ledger_claims(data_dir)
    todo = [(p, d, b) for p, d, b in res if (not refs or CR.ref_of(d) in refs) and any(cid not in decided for cid, _ in CR.claim_ids(d))]
    print(f"{len(todo)} correction(s) with undecided claims. Reviewer: {by}. Keys: a = accept, r = reject, s = skip, q = quit.")
    written = 0
    for path, doc, bad in todo:
        show(doc, bad, cl, decided, pol)
        act = ask("decision a/r/s/q", "s").lower()
        if act.startswith("q"):
            break
        if act.startswith("s"):
            continue
        cids = [cid for cid, _ in CR.claim_ids(doc) if cid not in decided]
        if act.startswith("a"):
            if bad:
                print("  check failed: an accept needs a clean check (fix the claim file, or reject with a reason).")
                continue
            if not (yes("  identity: the model number is visible and matches the entity") and yes("  the fact is visible as proposed")
                    and yes("  conditions and the domain disposition are acceptable")):
                print("  not accepted (all three must hold). Reject with a reason, or skip.")
                continue
            ev = doc.get("evidence") or {}
            changed = False
            for n, im in enumerate(ev.get("images") or [], 1):
                if not im.get("transcription"):
                    t = ask(f"  transcription of photo {n} (model number + fact as printed, <= {CR.MAX_TRANSCRIPTION} chars)")
                    if not t or len(t) > CR.MAX_TRANSCRIPTION:
                        print("  a transcription (<= 125 chars) is required for a photo; not accepted.")
                        break
                    im["transcription"] = CR.scrub(t, CR.MAX_TRANSCRIPTION); changed = True
            else:
                if changed:
                    path.write_text(CR._dump(doc))
                reason = ask("  reason", default_reason(doc))
                lines = [decision_line(cid, "accept_claim", by, reason, CR.pointer(doc), data_dir=data_dir) for cid in cids]
                append(lines, data_dir); written += len(lines)
                print(f"  accepted: {', '.join(cids)}")
            continue
        if act.startswith("r"):
            keys = list(CR.FAST_REJECT)
            for n, k in enumerate(keys, 1):
                print(f"   {n}. {k}: {CR.FAST_REJECT[k]}")
            pick = ask("  reason (1-5 or your own words)")
            reason = CR.FAST_REJECT[keys[int(pick) - 1]] if pick.isdigit() and 1 <= int(pick) <= len(keys) else pick
            lines = [decision_line(cid, "reject_claim", by, reason, CR.pointer(doc), data_dir=data_dir) for cid in cids]
            append(lines, data_dir); written += len(lines)
            print(f"  rejected: {', '.join(cids)}")
    print(f"{written} ledger line(s) appended to {ledger_path(data_dir)}. Next: rebuild, then close the issues (team/queue/corrections.md).")


def revert(cid, by, data_dir=None):
    doc = next((d for _, d in CR.load(data_dir) if cid in {c for c, _ in CR.claim_ids(d)}), None)
    if doc is None:
        raise SystemExit(f"{cid}: no claim file defines it")
    reason = ask(f"reason to reject {cid}")
    append([decision_line(cid, "reject_claim", by, reason, CR.pointer(doc), data_dir=data_dir)], data_dir)
    print(f"{cid}: reject_claim appended; the value is gone from the next build.")


def seed_links(seed_file, data_dir=None, repo=None, key="hw.dram_type"):
    """team/queue/ssd-dram-seed.md (A2: family ids + config ids, no values) -> one prefilled issue-form link per family. Posts nothing."""
    cl = CR.Catalogue(data_dir)
    repo = repo or CR.site_repo()
    out = []
    for ln in Path(seed_file).read_text().splitlines():
        ids = [x for x in re.findall(r"[a-z0-9][a-z0-9-]{2,95}", ln) if x in cl.cat]
        if not ids:
            continue
        fam = next((x for x in ids if cl.kind.get(x) == "family"), None)
        configs = [x for x in dict.fromkeys(ids) if x != fam]
        if not configs:
            continue
        fams = {cl.family.get(x) for x in configs}
        if fam is None and len(fams) == 1 and None not in fams and cl.kind.get(next(iter(fams))) == "family":
            fam = next(iter(fams))          # every listed config sits in one family: the claim is family-scoped, configs listed explicitly
        ent = fam or configs[0]
        payload = {"entity_id": ent, "key": key, "shown_value": "unknown", "build": "seed"}
        q = {"template": "field-correction.yml", "title": f"Specification correction: {ent} {key}", "payload": json.dumps(payload),
             "applies_to": "\n".join(configs) if (fam or len(configs) > 1) else ""}
        out.append((ent, len(configs), f"https://github.com/{repo}/issues/new?{urllib.parse.urlencode(q)}"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("refs", nargs="*")
    ap.add_argument("--by", help="your reviewer handle (asked once otherwise)")
    ap.add_argument("--revert")
    ap.add_argument("--seed")
    ap.add_argument("--key", default="hw.dram_type", help="--seed: the spec key of the family fact")
    ap.add_argument("--data", default=None)
    a = ap.parse_args()
    if a.seed:
        for ent, n, url in seed_links(a.seed, a.data, key=a.key):
            print(f"{ent} ({n} configurations):\n  {url}")
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise SystemExit("review_corrections.py is run by a person at a terminal (no TTY: refusing). Agents never write ledger lines.")
    by = a.by or ask("your reviewer handle (GitHub handle of the owner or a named maintainer)")
    if not valid_handle(by):
        raise SystemExit(f"{by!r} is not a reviewer handle")
    if a.revert:
        revert(a.revert, by, a.data)
    else:
        review(set(a.refs), by, a.data)


if __name__ == "__main__":
    main()
