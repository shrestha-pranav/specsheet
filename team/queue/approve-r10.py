#!/usr/bin/env python3
"""Coordinator (owner-delegated 2026-11-26): approve the 13 pending r10 policies (NOT claim/mfr-monitor-aoc@3). Run from ~/projects/specsheet:
    python3 -I team/queue/approve-r10.py
Only touches `approval: {state: pending}` lines inside claim_policies/relation_policies for the ids below."""
import re

WANT = {
    "claim/mfr-monitor-structured@12", "claim/derive-tuv-eye-comfort-5star@6", "claim/mfr-monitor-benq@5",
    "claim/mfr-monitor-dell@3", "rel/source-stated-hierarchy@17",                       # A2-ref monitors
    "claim/document-power-pdo@5", "claim/spec-image-power-pdo@3", "claim/hub-document-power-pdo@3",  # A2-pb re-pins
    "claim/mfr-power-banks-structured@10", "claim/derive-samsung-sfc2-pps@3", "claim/mfr-power-stations-structured@10",
    "claim/document-tv-ports@3", "rel/bundle-contents@10",                              # A3-fix review-10
}
p = "data/decisions/policies.yaml"
lines = open(p).read().split("\n")
cur = sec = None
done = set()
for i, l in enumerate(lines):
    if re.match(r"^[a-z_]+:", l):
        sec = l.split(":")[0]
    m = re.match(r"^- id: (\S+)", l)
    if m:
        cur = m.group(1)
    if cur in WANT and sec in ("claim_policies", "relation_policies") and l.strip() == "approval: {state: pending}":
        lines[i] = l.replace("{state: pending}", '{state: approved, by: coordinator-delegated, at: "2026-11-26"}')
        done.add(cur)
open(p, "w").write("\n".join(lines))
print("approved:", len(done), "missing:", sorted(WANT - done))
