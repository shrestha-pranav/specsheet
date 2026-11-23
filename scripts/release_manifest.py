#!/usr/bin/env python3
"""Release manifest + size budget (review 2 risks 1 and 5). Called by scripts/release.sh; small, git-tracked output in releases/.

  python3 -I scripts/release_manifest.py measure  [--site docs] [--gh-pages REF]           -> JSON report on stdout, exit 2 if over the fail budget
  python3 -I scripts/release_manifest.py write    --gh-pages COMMIT [--site docs]          -> releases/<release-id>.json + releases/index.jsonl line

A manifest identifies everything a release was made from, so a pinned release can be reconstructed and compared after parsers/policies move:
  inputs   raw snapshot digest (source|ref|snapshot over every observation imported), parser id@version + fingerprint per source, profile/
           normaliser/importer digests, policy file + policy-lock digest + approval states + parser drift, ledger digest, id registry digest
           (all recorded by scripts/import.py in the sqlite meta table `inputs`), accepted_digest
  code     git HEAD, dirty flag, and a content digest of the tracked source tree (scripts/ crawler/ schemas/ research/ data/ docs app shell)
  output   tree digest of the published site (path + sha256 of every file), logical bytes, file count, gzip bytes (transfer estimate),
           bytes/files changed versus the previous gh-pages snapshot, packed size of the gh-pages snapshot, packed size of the repository
  budget   data/release-budget.json: warn / fail thresholds; raising a fail threshold is an explicit, reviewed edit of that file.
Generated JSON never goes to main: it is published from an orphan single-commit gh-pages branch (release.sh); main keeps these manifests.
"""
import argparse, hashlib, json, sqlite3, subprocess, sys, time, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIB = 1024 * 1024
SOURCE_DIRS = ["scripts", "crawler", "schemas", "research", "data/decisions", "data/_ids", "docs/index.html", "docs/app.js", "docs/styles.css", "docs/favicon.svg"]


def git(*a, check=True):
    p = subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f"git {' '.join(a)}: {p.stderr.strip()}")
    return p.stdout.strip() if p.returncode == 0 else None


def budget():
    p = ROOT / "data" / "release-budget.json"
    return json.loads(p.read_text())


def evaluate(api_bytes, pack_bytes, b):
    """-> (state, messages). state: ok | warn | fail. Pure (unit-tested in tests/test_adversarial.py)."""
    msgs, state = [], "ok"
    if api_bytes > b["api_fail_mib"] * MIB:
        state = "fail"; msgs.append(f"live API {api_bytes / MIB:.1f} MiB > fail budget {b['api_fail_mib']} MiB (raise it only by editing data/release-budget.json)")
    elif api_bytes > b["api_warn_mib"] * MIB:
        state = "warn"; msgs.append(f"live API {api_bytes / MIB:.1f} MiB > warn budget {b['api_warn_mib']} MiB")
    if pack_bytes is not None:
        if pack_bytes > b["repo_pack_migrate_mib"] * MIB:
            state = "fail" if state == "fail" else "warn"; msgs.append(f"packed repository {pack_bytes / MIB:.1f} MiB > migration trigger {b['repo_pack_migrate_mib']} MiB: plan the move to object storage")
        elif pack_bytes > b["repo_pack_warn_mib"] * MIB:
            state = "fail" if state == "fail" else "warn"; msgs.append(f"packed repository {pack_bytes / MIB:.1f} MiB > warn {b['repo_pack_warn_mib']} MiB")
    return state, msgs


def blob_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree(site):
    """-> {relpath: (size, sha256, git blob sha1, gzip size)} for every file of the site (dotfiles included)."""
    out = {}
    for f in sorted(site.rglob("*")):
        if f.is_file():
            d = f.read_bytes()
            out[f.relative_to(site).as_posix()] = (len(d), hashlib.sha256(d).hexdigest(), blob_sha1(d), len(zlib.compress(d, 6)))
    return out


def source_digest():
    files = git("ls-files", "-z", "--", *SOURCE_DIRS).split("\0")
    h = hashlib.sha256()
    for f in sorted(x for x in files if x):
        p = ROOT / f
        h.update(f.encode() + b"\0" + (p.read_bytes() if p.exists() else b"<deleted>") + b"\0")
    return "sha256:" + h.hexdigest()


def pack_size(ref):
    """Bytes of a pack holding exactly the objects reachable from ref (the size a fresh clone of that branch downloads)."""
    revs = subprocess.run(["git", "-C", str(ROOT), "rev-list", "--objects", ref], capture_output=True, check=True).stdout
    p = subprocess.run(["git", "-C", str(ROOT), "pack-objects", "--stdout", "-q"], input=revs, capture_output=True, check=True)
    return len(p.stdout)


def repo_pack():
    kv = dict(l.split(": ", 1) for l in git("count-objects", "-v").splitlines())
    return (int(kv.get("size-pack", 0)) + int(kv.get("size", 0))) * 1024


def measure(site, prev_ref):
    t = tree(site)
    api = {k: v for k, v in t.items() if k.startswith("api/")}
    prev = {}
    if prev_ref and git("rev-parse", "--verify", "-q", prev_ref, check=False):
        for ln in (git("ls-tree", "-r", "-l", prev_ref) or "").splitlines():
            meta, path = ln.split("\t", 1)
            _mode, _typ, sha, size = meta.split()
            prev[path] = sha
    changed = [k for k, v in t.items() if prev.get(k) != v[2]]
    h = hashlib.sha256()
    for k, v in t.items():
        h.update(f"{k}\0{v[1]}\n".encode())
    return {"tree_digest": "sha256:" + h.hexdigest(), "files": len(t), "logical_bytes": sum(v[0] for v in t.values()),
            "api_files": len(api), "api_logical_bytes": sum(v[0] for v in api.values()), "api_gzip_bytes": sum(v[3] for v in api.values()),
            "vs_previous": {"ref": prev_ref if prev else None, "changed_files": len(changed), "changed_bytes": sum(t[k][0] for k in changed),
                            "removed_files": len(set(prev) - set(t))}}


def db_inputs():
    con = sqlite3.connect(ROOT / "state" / "specsheet.sqlite")
    meta = dict(con.execute("SELECT k, v FROM meta"))
    if meta.get("scope") != "full":
        raise SystemExit("state/specsheet.sqlite is not a full import")
    return {"accepted_digest": meta.get("accepted_digest"), "imported_at": meta.get("built_at"), **json.loads(meta.get("inputs") or "{}")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["measure", "write"])
    ap.add_argument("--site", default=str(ROOT / "docs"))
    ap.add_argument("--gh-pages", help="measure: previous snapshot ref to diff against; write: the new gh-pages commit")
    ap.add_argument("--prev", default="gh-pages", help="write: previous snapshot ref (default: gh-pages before update)")
    a = ap.parse_args()
    site = Path(a.site)
    b = budget()
    if a.cmd == "measure":
        out = measure(site, a.gh_pages or "gh-pages")
        out["repo_pack_bytes"] = pack_size("main")
        out["budget_state"], out["budget_messages"] = evaluate(out["api_logical_bytes"], out["repo_pack_bytes"], b)
        print(json.dumps(out, indent=1))
        sys.exit(2 if out["budget_state"] == "fail" else 0)
    inp = db_inputs()
    out = measure(site, a.prev)
    if a.gh_pages:
        out["gh_pages_commit"] = git("rev-parse", a.gh_pages)
        out["gh_pages_pack_bytes"] = pack_size(a.gh_pages)
    rp = pack_size("main")          # what a fresh clone of the source branch downloads (budget); count-objects is informational
    state, msgs = evaluate(out["api_logical_bytes"], rp, b)
    rid = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + (inp.get("accepted_digest") or "x")[:8]
    man = {"format": "specsheet.release/1", "release": rid, "created_at": time.strftime("%FT%TZ", time.gmtime()),
           "code": {"git_head": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", *SOURCE_DIRS)), "source_digest": source_digest()},
           "inputs": inp, "output": out, "repository": {"main_pack_bytes": rp, "local_object_store_bytes": repo_pack()},
           "budget": {"state": state, "messages": msgs, "limits": b}}
    d = ROOT / "releases"
    d.mkdir(exist_ok=True)
    (d / f"{rid}.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    with (d / "index.jsonl").open("a") as f:
        f.write(json.dumps({"release": rid, "accepted_digest": inp.get("accepted_digest"), "tree_digest": out["tree_digest"],
                            "gh_pages_commit": out.get("gh_pages_commit"), "api_logical_bytes": out["api_logical_bytes"], "budget": state}, sort_keys=True) + "\n")
    print(json.dumps({"release": rid, "manifest": f"releases/{rid}.json", "budget": state, "messages": msgs,
                      "api_mib": round(out["api_logical_bytes"] / MIB, 1), "api_files": out["api_files"], "gh_pages_pack_mib": round(out.get("gh_pages_pack_bytes", 0) / MIB, 1),
                      "repo_pack_mib": round(rp / MIB, 1)}, indent=1))
    if state == "fail":
        sys.exit(2)


if __name__ == "__main__":
    main()
