# A3-gov 2026-11-26: policy approval gate (brief coord-2026-11-26-approval-gate)
Decisions:
- Only a policy with approval {state: approved, by, at} auto-accepts claims (claim_state) or approves relations (relation_state). Pending, missing or half-filled approval => claims candidate (preview only), relations proposed. A ledger decision still works as before.
- I applied the claim hunk of the draft patch as written. I did NOT apply its relation hunk. That hunk skipped *validation* of pending relation policies, which weakens governance, and it never gated relation_state. The gate now sits in relation_state, and every policy is still validated (test_pending_policy_still_validated).
- Held-back accounting: `Decisions.held` counts unique claim ids and relation triples per unapproved policy. A claim that a later approved policy accepts is not counted. approvals() now reports "approved-incomplete" when by/at is missing, so it shows up in pending_approval.
- Governance output: import.py prints one stderr line per unapproved policy, which therefore also appears in release.sh output: `governance: <id> is <state>: holding back N claims, M relations`. The import JSON gets `governance.held_by_pending: {id: {claims, relations, approval}}`.
Real data (step 4): I built HEAD code in a worktree (raw/ symlinked, then removed) and diffed it against the new code. Only AOC differs:
- 2053 claims of claim/mfr-monitor-aoc@3 are held (monitors accepted 41367 -> 39314). Every other category's claims_review is identical.
- Trusted diffs are the 18 aoc-* index rows / product specs (the withheld not_published stubs are gone), the monitor facets, and an index page boundary shift (lenovo rows have identical content). The preview gains 16 aoc-* entities.
- Pre-existing, unrelated: v1_publish sources_for numbers inherited local source ids (s2/s3) nondeterministically between builds (e.g. lenovo-63bdgar6us, same URLs and values). It needs a sort if byte-stable output matters.
Final: bare `import.py --strict-parsers` and `build.py` under flock, rc 0. All 51 tests/test_*.py pass.
Files changed (shared): scripts/decisions.py (gate, held, approvals), scripts/import.py (+5 lines governance output), ARCHITECTURE.md §15.8 (one sentence).
Tests: fixtures now approve explicitly (by fixture-approver, at 2026-11-26) in test_adversarial, corrections, new_category, r6, r7, r8, source_policy. Real-policy copies in r7/r8 keep their real approval. The gate was not weakened.
New: tests/test_approval_gate.py, 11 tests:
- unit: pending => candidate/proposed + held counts; approved => accepted; half-filled approval is not approval; validation still applies; a later approved policy wins.
- build: pending fixture => nothing in the trusted index and values in preview; approving (lock unchanged) => accepted next build and revision variant_of approved; held_by_pending listed.
Not touched: data/decisions/policies.yaml (AOC stays pending). docs/index.html build-id churn comes from build.py.
Open: should release.sh fail, rather than warn, when held_by_pending is non-empty? Currently it only warns.
