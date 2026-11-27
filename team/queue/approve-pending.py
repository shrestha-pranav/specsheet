#!/usr/bin/env python3
"""Coordinator (owner-delegated 2026-11-26: 'Consider all policies approved, just keep a running tally').
Approves every ACTIVE pending policy except HOLD, and appends each to team/queue/approvals-tally.md.
Usage (from ~/projects/specsheet): python3 -I team/queue/approve-pending.py "<round label>" [--dry]"""
import re, sys, datetime
HOLD = {"claim/mfr-monitor-aoc@3"}          # licensing hold: www.aoc.com free:false, parked owner decision (b)
label = sys.argv[1] if len(sys.argv) > 1 else "unlabelled"; dry = "--dry" in sys.argv
today = datetime.date.today().isoformat()
p = "data/decisions/policies.yaml"; lines = open(p).read().split("\n")
cur = sec = None; done = []
for i, l in enumerate(lines):
    if re.match(r"^[a-z_]+:", l): sec = l.split(":")[0]
    m = re.match(r"^- id: (\S+)", l)
    if m: cur = m.group(1)
    if sec in ("claim_policies", "relation_policies") and cur not in HOLD and l.strip() == "approval: {state: pending}":
        lines[i] = l.replace("{state: pending}", '{state: approved, by: coordinator-delegated, at: "%s"}' % today); done.append(cur)
print("approve:", done, "held:", sorted(HOLD))
if not dry:
    open(p, "w").write("\n".join(lines))
    with open("team/queue/approvals-tally.md", "a") as f:
        for d in done: f.write(f"| {today} | {d} | see report | {label} |\n")
