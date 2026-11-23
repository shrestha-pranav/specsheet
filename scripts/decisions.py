"""Decision ledger + versioned auto-accept policies (review P0-1). Both live in git under data/decisions/ and are the ONLY inputs,
besides raw/, that decide what is published as accepted. state/specsheet.sqlite is a projection of raw + these files.

data/decisions/policies.yaml  versioned policies; a claim/relation accepted by a policy records the policy id.
data/decisions/ledger.jsonl   append-only human decisions, later lines win for the same target:
  {"id": "d_...", "at": ISO, "by": "<handle>", "action": "accept_claim|reject_claim", "claim": "c_...", "reason": "..."}
  {"action": "approve_relation|reject_relation", "from": "<entity id>", "type": "<relation type>", "to": "<entity id>", ...}
  {"action": "merge", "anchors": ["<anchor>", ...], ...}            # allows a quarantined multi-hit observation to unify entities
  {"action": "split", "anchors": ["<anchor>", ...], ...}            # vetoes a merge/relation between entities holding these anchors
LLM agents may PROPOSE ledger lines in a report; only a human handle may appear in `by` for approve/merge/accept.

Governance (review 2 risk 1):
  - a policy's MEANING is frozen per id: data/decisions/policy-lock.jsonl records sha256(canonical policy minus `approval`) the first time
    an id is seen; a later import whose content differs under the same id FAILS (issue @N+1 instead). A locked id may not disappear:
    move it to `retired_policies` verbatim (it then never applies). Approving a policy (filling `approval`) does not change its hash.
  - every active claim policy needs an explicit key allowlist (`match.keys`: list, or {source_id: [keys]}) plus `source_ids` and
    `extractors`; relation policies are explicit `rules` of {method, types, parsers} (exact method, exact parser id@version), no globs.
  - `audit: {by, at, evidence, parsers: {extractor: parser_fingerprint}}` records what was audited; `approval: {state: pending|approved,
    by, at}` records who approved it. Parser drift (current fingerprint != audited one) is reported, and is fatal under --strict-parsers.
"""
import fnmatch, hashlib, json, time
from pathlib import Path

import yaml


def policy_hash(p):
    body = {k: v for k, v in p.items() if k not in ("approval", "retired")}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def _legacy(a):
    """v2 anchor -> v1 form (identity.legacy_anchor; duplicated to keep this module import-free)."""
    p = a.split("|")
    return "|".join([p[1]] + p[3:]) if p[0] == "v2" and len(p) == 7 else a


def _hit(ledger_anchor, a):
    return ledger_anchor == a or ledger_anchor == _legacy(a)

ACTIONS = {"accept_claim", "reject_claim", "approve_relation", "reject_relation", "merge", "split"}


class Decisions:
    def __init__(self, data_dir: Path):
        self.dir = data_dir / "decisions"
        p = self.dir / "policies.yaml"
        doc = yaml.safe_load(p.read_text()) if p.exists() else {}
        self.format = doc.get("format")
        self.claim_policies = doc.get("claim_policies") or []
        self.relation_policies = doc.get("relation_policies") or []
        self.retired_policies = doc.get("retired_policies") or []
        self.policy_doc = doc
        self.lock_path = self.dir / "policy-lock.jsonl"
        self._validate()
        self.claims, self.relations, self.merges, self.splits = {}, {}, [], []
        self.lines = 0
        lp = self.dir / "ledger.jsonl"
        if lp.exists():
            for n, ln in enumerate(lp.read_text().splitlines(), 1):
                if not ln.strip() or ln.lstrip().startswith("#"):
                    continue
                d = json.loads(ln)
                if d.get("action") not in ACTIONS or not d.get("id") or not d.get("by"):
                    raise SystemExit(f"ledger.jsonl:{n}: needs id, by and an action in {sorted(ACTIONS)}")
                self.lines += 1
                a = d["action"]
                if a in ("accept_claim", "reject_claim"):
                    self.claims[d["claim"]] = d
                elif a in ("approve_relation", "reject_relation"):
                    self.relations[(d["from"], d["type"], d["to"])] = d
                elif a == "merge":
                    self.merges.append(set(d["anchors"]))
                else:
                    self.splits.append(set(d["anchors"]))

    # ------------------------------------------------------------------ governance
    def active(self):
        return self.claim_policies + self.relation_policies

    def _validate(self):
        ids = [p["id"] for p in self.active() + self.retired_policies]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise SystemExit(f"policies.yaml: duplicate policy ids {dup}")
        for p in self.claim_policies:
            m = p.get("match") or {}
            miss = [f for f in ("keys", "source_ids", "extractors") if not m.get(f)]
            if miss:
                raise SystemExit(f"policies.yaml {p['id']}: claim policies need explicit {miss} (review 2: no type-class or open-ended acceptance)")
            if isinstance(m["keys"], dict) and set(m["keys"]) - set(m["source_ids"]):
                raise SystemExit(f"policies.yaml {p['id']}: keys{{source}} names a source not in source_ids")
        for p in self.relation_policies:
            for r in p.get("rules") or []:
                if any(ch in r.get("method", "*") for ch in "*?[") or not r.get("types") or not r.get("parsers"):
                    raise SystemExit(f"policies.yaml {p['id']}: relation rules need an exact method, types and parsers (no globs)")
            if p.get("methods"):
                raise SystemExit(f"policies.yaml {p['id']}: `methods` globs are retired; use explicit `rules`")

    def check_lock(self, write=True):
        """Freeze policy meaning per id. -> (appended ids, digest over all locked hashes). Raises on a changed or vanished id."""
        lock = {}
        if self.lock_path.exists():
            for ln in self.lock_path.read_text().splitlines():
                if ln.strip():
                    r = json.loads(ln)
                    lock.setdefault(r["id"], r["sha256"])
        seen, new = set(), []
        for p in self.active() + self.retired_policies:
            h = policy_hash(p)
            seen.add(p["id"])
            if p["id"] in lock and lock[p["id"]] != h:
                raise SystemExit(f"policies.yaml: content of {p['id']} changed under the same id (locked {lock[p['id']][:19]}, now {h[:19]}). "
                                 "A policy's meaning is frozen: issue a new id (@N+1) and move the old one to retired_policies verbatim.")
            if p["id"] not in lock:
                new.append({"id": p["id"], "sha256": h, "at": time.strftime("%FT%TZ", time.gmtime())})
                lock[p["id"]] = h
        gone = sorted(set(lock) - seen)
        if gone:
            raise SystemExit(f"policies.yaml: locked policies {gone} disappeared; keep them under retired_policies (verbatim)")
        if new and write:
            with self.lock_path.open("a") as f:
                for r in new:
                    f.write(json.dumps(r, sort_keys=True) + "\n")
        return [r["id"] for r in new], "sha256:" + hashlib.sha256(json.dumps(sorted(lock.items())).encode()).hexdigest()

    def parser_drift(self, current):
        """current: {extractor: fingerprint}. -> [(policy id, extractor, audited, current)] where an audited parser changed."""
        out = []
        for p in self.active():
            for ex, fp in sorted(((p.get("audit") or {}).get("parsers") or {}).items()):
                if ex in current and current[ex] != fp:
                    out.append((p["id"], ex, fp, current[ex]))
        return out

    def approvals(self):
        return {p["id"]: ((p.get("approval") or {}).get("state") or "missing") for p in self.active()}

    # ------------------------------------------------------------------ claims
    def claim_state(self, cid, ctx):
        """ctx: source_id, extractor (name@ver), key, spec_type, kind, tier, status, normalized (bool). -> (state, decision id)."""
        d = self.claims.get(cid)
        if d:
            return ("accepted" if d["action"] == "accept_claim" else "rejected"), d["id"]
        for p in self.claim_policies:
            if self._match(p, ctx):
                return "accepted", p["id"]
        return "candidate", None

    @staticmethod
    def _match(p, ctx):
        m = p.get("match") or {}
        for fld in ("source_ids", "extractors", "kinds", "tiers", "statuses"):
            allowed = m.get(fld)
            if allowed is not None and ctx.get(fld[:-1] if fld != "statuses" else "status") not in allowed:
                return False
        if m.get("spec_types") is not None and ctx.get("spec_type") not in m["spec_types"] and ctx["key"] not in (m.get("also_keys") or []):
            return False
        keys, excl = m.get("keys"), m.get("exclude_keys") or []
        if isinstance(keys, dict):
            keys = keys.get(ctx.get("source_id")) or []
        if keys is not None and ctx["key"] not in keys:
            return False
        if ctx["key"] in excl or any(ctx["key"].startswith(x[:-1]) for x in excl if x.endswith("*")):
            return False
        if m.get("require_normalized", True) and ctx["status"] == "known" and not ctx["normalized"]:
            return False
        return True

    # ------------------------------------------------------------------ relations
    def relation_state(self, frm, typ, to, method, parser=None):
        d = self.relations.get((frm, typ, to))
        if d:
            return ("approved" if d["action"] == "approve_relation" else "rejected"), d["id"]
        for p in self.relation_policies:
            for r in p.get("rules") or []:
                if r["method"] == method and typ in r["types"] and parser in r["parsers"]:
                    return "approved", p["id"]
        return "proposed", None

    def merge_allowed(self, anchors):
        anchors = set(anchors)
        cover = lambda m: all(any(_hit(x, a) for x in m) for a in anchors)
        n_split = lambda s: sum(1 for a in anchors if any(_hit(x, a) for x in s))
        return any(cover(m) for m in self.merges) and not any(n_split(s) > 1 for s in self.splits)

    def vetoed(self, a1, a2):
        return any(any(_hit(x, a1) for x in s) and any(_hit(x, a2) for x in s) for s in self.splits)
