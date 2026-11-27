#!/usr/bin/env python3
"""Coordinator ruling 2026-11-26 on team/queue/terms-audit-r11.yaml.
A (terms bar automated access), R (robots names Claude agents), X (blocked) => crawl human_only.
B-only (personal non-commercial use licence, no automated-access clause) => stays crawl agent: owner direction
'datasets first, licensing later' makes it a licensing question; recorded as to_clear for owner review.
Netgear: s12 names NETGEAR websites => A for www.netgear.com AND www.downloads.netgear.com / downloads1.netgear.com.
Stay-agent proposals: evidence upgraded to the audit's fetched evidence."""
import re, sys, yaml
P = "data/source-policy.yaml"
prop = {p["domain"]: p for p in yaml.safe_load(open("team/queue/terms-audit-r11.yaml"))["proposals"]}
net = prop.get("www.netgear.com")
for extra in ("www.downloads.netgear.com", "downloads1.netgear.com"):
    prop[extra] = {"domain": extra, "crawl": "human_only", "basis": ["A"], "evidence": net["evidence"],
                   "note": "coordinator ruling r11: NETGEAR terms s12 bars automated tools/web crawlers on NETGEAR websites (supersedes 2026-11-25.5 subscription-only reading)"}
lines = open(P).read().split("\n")
done, skipped, deferred = [], [], []
for i, l in enumerate(lines):
    m = re.match(r"^  - \{domain: ([^,]+),", l)
    if not m or m.group(1) not in prop:
        continue
    d = m.group(1); p = prop[d]
    try:
        e = yaml.safe_load(l.strip()[2:])
    except Exception:
        skipped.append(d); continue
    if not isinstance(e, dict):
        skipped.append(d); continue
    basis = set(p.get("basis") or [])
    if p.get("crawl") == "human_only" and basis & {"A", "R", "X"}:
        e["crawl"] = "human_only"; e["evidence"] = p["evidence"]
        e["to_clear"] = (p.get("note", "") + " " if p.get("note") else "") + "Terms/robots audit r11 (basis " + "+".join(sorted(basis)) + "). Stored values stay published pending owner decision (parked (a)); no new agent fetches."
        done.append((d, "human_only", "+".join(sorted(basis)), p.get("published_values")))
    elif p.get("crawl") == "human_only":
        e["evidence"] = p["evidence"]
        e["to_clear"] = "LICENSING (deferred per owner 2026-11-26): site licence limits use to personal non-commercial (audit r11 basis B); no automated-access clause, so crawl stays agent. Owner review."
        deferred.append((d, p.get("published_values")))
    else:
        e["evidence"] = p["evidence"]; done.append((d, "agent (evidence upgraded)", "", p.get("published_values")))
    lines[i] = "  - " + yaml.safe_dump(e, default_flow_style=True, sort_keys=False, width=100000, allow_unicode=True).strip()
s = "\n".join(lines)
v = s.split('policy_version: "')[1].split('"')[0]; dd, n = v.rsplit(".", 1); nv = f"{dd}.{int(n)+1}"
s = s.replace(f'policy_version: "{v}"', f'policy_version: "{nv}"', 1)
flips = [x[0] for x in done if x[1] == "human_only"]
s = s.replace("changelog:\n", "changelog:\n  - {version: \"%s\", by: coordinator, note: \"Terms audit r11 (A5, team/queue/terms-audit-r11.yaml) applied: %d hosts crawl human_only on basis A/R/X (%s). %d basis-B-only hosts (personal non-commercial licence, no automated-access clause) stay agent with to_clear LICENSING, deferred per owner 2026-11-26 (%s). NETGEAR s12 ruling covers all 3 netgear hosts. Stored values unchanged (parked (a)).\"}\n" % (nv, len(flips), ", ".join(flips), len(deferred), ", ".join(x[0] for x in deferred)), 1)
open(P, "w").write(s)
print("version", nv); print("flips", len(flips), flips); print("deferred B", deferred); print("skipped", skipped)
print("missing", sorted(set(prop) - {x[0] for x in done} - {x[0] for x in deferred} - set(skipped)))
