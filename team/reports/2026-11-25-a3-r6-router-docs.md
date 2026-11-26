# A3-docs r6: router doc parser (docspec-router@2, r3@2), 2026-11-25
**Final:** bare `import.py --strict-parsers` rc 0, parser_drift 0 (r3@2 lock line written by this import). `build.py` rc 0, both under flock.
release.sh not run. Nothing committed.

## Decisions (open first)
- **OPEN, coordinator: approve `claim/document-spec-r3@2`** (`approval: {state: pending}`, pin `docspec-attach-r3@2`).
  - @1 moved verbatim to retired_policies with a `retired:` line.
  - TV/laptop claims (same docspec-tv@1 / docspec-laptop@1, same 105 TV claims as @1) now ride on r3@2, so they are pending until approval.
- **New router keys:** port.lan_max_mbps, hw.cpu_cores, hw.cpu_ghz, hw.soc_vendor. The router adapters already emit these profile keys.
- **Routers read datasheet / spec_sheet docs only.** 61 manuals/QSGs are skipped: they cover model families.
- **Row-scoped binding (routers):** when a sheet names another catalogued same-brand entity, including one linked from the same page
  (which @1 let through), a fact binds only if its own row/group quotes this entity and no sibling (`identity_scope: row`).
  Unlinked siblings still fail closed (multi_model_other_page).
- **hw.soc_model not read:** no stored sheet prints a part number. GL.iNet's "Qualcomm Quad-core" gives soc_vendor.

## Parser (docspec-router@2, affirmative only; full rules in the docstring)
- **NETGEAR bullet prose:**
  - Column-aware items; only items that open with a key phrase are read ("WiFi 7 BE9300 Router Tri-band WiFi",
    "- 6 GHz (2x2)", "(1) 2.5 Gbps internet port", "(N) .. LAN ports" summed, "1 WAN & 4 LAN").
  - Satellite blocks are never read. A port group with an unreadable line reads no LAN facts.
- **Other layouts:** GL.iNet in-cell sub-labels ("WAN Port: 1 x 2.5G Port"), Ubiquiti cells with continuation lines, the TS page heading.
- **Conflicts:** groups that disagree read nothing (UDM-Pro WAN 1G vs SFP+ 10G). 802.11ax + 6 GHz is not promoted to 6E.

## Fill deltas
- **Replay:** 65 router docs parsed, 39 entities. 201 claims: 119 corroborate, 82 new, 0 disagree with other official claims.
- **Published routers (334 rows, before -> after):**
  - wan_speed 191 -> 196, lan_count 164 -> 187, lan_max 158 -> 181, cpu_cores 103 -> 117.
  - band_count 255 -> 257, has_6ghz 251 -> 252, generation 315 (doc values corroborate only).
- **WAN 2.5G+ query:** +5 new WAN speeds, 15 agree. Most stored sheets are for models whose page already states WAN.
- **router-wifi7-6ghz:** unchanged (fill 0.8214, passes, 79 matches). Weakest key rate_5_mbps is not read from docs. has_6ghz 136/140.
- **TV:** unchanged vs r3@1 (105 claims). Multi-model proposals 37 -> 59 (+22 router, fail closed: mostly kits naming catalogued units).

## Fixtures + files
- **Tests:** `tests/test_docspec_router2.py` (new, 12 tests):
  - NETGEAR bullets, prose not read, kit satellite, partial port group, WAN & LAN split.
  - GL.iNet in-cell, Ubiquiti cells + UDM-Pro conflict, ax+6GHz not promoted.
  - Multi-model sheet does not cross-bind; a router manual is not read.
- **Mine:** `crawler/adapters/_docspec_router.py`.
- **Shared:** `scripts/docspec_r3.py` (transform @2, router kinds, row scope, keys); `tests/test_docspec_r3.py` (one expectation +row);
  `data/decisions/policies.yaml` (r3@2 pending, @1 retired).
- **Not touched:** Dell/power-station adapters, source-policy.yaml. **Data:** append-only parsed-spec caches.
