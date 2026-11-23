"""Decision ledger + versioned auto-accept policies (review P0-1). Both live in git under data/decisions/ and are the ONLY inputs,
besides raw/, that decide what is published as accepted. state/specsheet.sqlite is a projection of raw + these files.

data/decisions/policies.yaml  versioned policies; a claim/relation accepted by a policy records the policy id.
data/decisions/ledger.jsonl   append-only human decisions, later lines win for the same target:
  {"id": "d_...", "at": ISO, "by": "<handle>", "action": "accept_claim|reject_claim", "claim": "c_...", "reason": "..."}
  {"action": "approve_relation|reject_relation", "from": "<entity id>", "type": "<relation type>", "to": "<entity id>", ...}
  {"action": "merge", "anchors": ["<anchor>", ...], ...}            # allows a quarantined multi-hit observation to unify entities
  {"action": "split", "anchors": ["<anchor>", ...], ...}            # vetoes a merge/relation between entities holding these anchors
LLM agents may PROPOSE ledger lines in a report; only a human handle may appear in `by` for approve/merge/accept.
"""
import fnmatch, json
from pathlib import Path

import yaml

ACTIONS = {"accept_claim", "reject_claim", "approve_relation", "reject_relation", "merge", "split"}


class Decisions:
    def __init__(self, data_dir: Path):
        self.dir = data_dir / "decisions"
        p = self.dir / "policies.yaml"
        doc = yaml.safe_load(p.read_text()) if p.exists() else {}
        self.format = doc.get("format")
        self.claim_policies = doc.get("claim_policies") or []
        self.relation_policies = doc.get("relation_policies") or []
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
        if keys is not None and ctx["key"] not in keys:
            return False
        if ctx["key"] in excl or any(ctx["key"].startswith(x[:-1]) for x in excl if x.endswith("*")):
            return False
        if m.get("require_normalized", True) and ctx["status"] == "known" and not ctx["normalized"]:
            return False
        return True

    # ------------------------------------------------------------------ relations
    def relation_state(self, frm, typ, to, method):
        d = self.relations.get((frm, typ, to))
        if d:
            return ("approved" if d["action"] == "approve_relation" else "rejected"), d["id"]
        for p in self.relation_policies:
            if any(fnmatch.fnmatchcase(method, pat) for pat in (p.get("methods") or [])) and (not p.get("types") or typ in p["types"]):
                return "approved", p["id"]
        return "proposed", None

    def merge_allowed(self, anchors):
        anchors = set(anchors)
        return any(anchors <= m for m in self.merges) and not any(len(anchors & s) > 1 for s in self.splits)

    def vetoed(self, a1, a2):
        return any(a1 in s and a2 in s for s in self.splits)
