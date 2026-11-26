# A3-fix: review-10 fixes (2026-11-26)
Done. Strict import (`--strict-parsers`) + build rc 0. 54 of 55 tests/test_*.py pass. test_match fails on recall only (0.84 / 0.75). The cause is held values, not code: listings from power banks (my pending pb@10) and A2-ref's pending monitor policies drop out. It clears once those are approved. No A2-ref monitor test fails.
1. P1-1 dependency bypass. `import.parent_supports`: a psref-split value publishes only if its parent literal is accepted, or is a no-decision candidate only because it does not normalise. That is probed as if normalised (`Decisions.policy_state`, which has no side effects): an APPROVED policy accepts it, or no policy at all covers its key (Memory Slots, which is what psref-split@1's rationale describes). If any pending or half-approved policy matches, the dependent is withheld. `docspec_r7tv` @3 builds its inventory only from TRUSTED hdmi.count (`import.trusted_probe`, using the write loop's mapping, cid, normalisation and ctx via `claim_state(record=False)`). Any disagreeing count voids it, and no probe means nothing is emitted.
   Tests in tests/test_review10.py: unit tests (gate, probe, inventory) and EndToEnd. EndToEnd runs on the real PSREF store with the parent policy pending, a pending policy on Memory Slots and psref-split@1 approved. Result: 0 dependents accepted, 0 in trusted index/products/R2 pack (which /v1 query and the MCP tools serve), 0 ram-upgradable preset matches. Preview keeps them. A control build shows every artifact carries them.
2. P1-2 pb_pps_r7@8. Negation now covers cannot / can't / won't / isn't / unable / incompatible / never / lacks, with any apostrophe. Model identity is exact after normalisation (own mfr_model / mfr_sku plus the model tokens inside them): P730 != P73, P73-PRO != P73. Both review probes now return None.
3. P1-3 _powerstation. `UPS_LIST_AFTER`: '10 ms or 20 ms', '10 ms / 20 ms', '10 ms, 20 ms' are unresolved in rows too. Lower bounds are never exact: 'or over / above / beyond / and higher', '=>', '&gt;=', '&ge;', '≧'. 'Backup UPS: <20ms, Online UPS: 0ms' still gives up to 20. Both probes are unresolved in rows and prose.
4. scripts/zero_trace.py plus tests/test_zero_trace.py. It scans every text file in docs/ (trusted and preview API, lookup/alias index, sitemap, llms.txt, sources.json) and api-worker/pack (records, bulk, index, match catalogue, presets). It checks for free:false URLs or bare domains, credit labels, and values that only free:false sources support (from the store, including candidates, as headline, alternative or index value).
   Live result: 27,923 files, 20 hosts, 2,045 AOC-only values on 177 entities, 0 traces. The fixture test shows each trace kind is caught.
Reissued as `approval: {state: pending}`. Old versions are retired verbatim with a retired line, and new ids are locked (policy-lock lines 173-177):
claim/mfr-power-banks-structured@9->@10, claim/derive-samsung-sfc2-pps@2->@3, claim/mfr-power-stations-structured@9->@10,
claim/document-tv-ports@2->@3 (transform docspec-attach-tvports@3), rel/bundle-contents@9->@10.
Parser bumps: anker/iniu/cuktech_powerbanks @7->@8, the five stations @8->@9.
Live value changes from code: 0.
- In-memory diff, HEAD parsers vs new, over every stored snapshot of the 8 sources: 0 claims changed (31 pd.pps, 36 ups.switchover_ms identical).
- psref-split accepted: 14,145 before and after.
- TV ports, A/B import with trust check vs trust-all: identical (22 claims, 11 models; every supporting hdmi.count is accepted).
Held until approval (expected removals): pb@10 1,236 claims (all 9 power-bank parsers, so trusted pd.pps drops 45->1), stations@10 1,463, tv-ports@3 22, sfc2@3 1, bundle@10 195 relations.
Shared-file changes:
- scripts/import.py: parent_supports, trusted_probe, DS7 call, pdid tuple.
- scripts/decisions.py: policy_state, claim_state record=.
- scripts/docspec_r7tv.py.
- crawler/adapters/{pb_pps_r7,anker_powerbanks,_powerstation,shopify_powerstations,ankersolix_stations}.py.
- data/decisions/policies.yaml (5 reissues and 5 retirements, text surgery only; A2-ref's entries untouched) and policy-lock.jsonl.
- Tests: test_review9 (TRUST_ALL), test_r6, test_r7, test_review3, test_r7_powerbank_pps (id bumps), test_a2_r6_dell (lines 101-103 only: stations pin @9).
- New: scripts/zero_trace.py, tests/test_review10.py, tests/test_zero_trace.py.
Open questions:
- (a) The rule that a parent with no covering policy is allowed keeps Memory Slots -> mem.slots/mem.soldered published (4,160). Confirm this reading of psref-split@1.
- (b) zero_trace is not wired into release.sh yet: coordinator's call.
