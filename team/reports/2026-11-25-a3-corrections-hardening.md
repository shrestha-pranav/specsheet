# A3 corrections hardening (Codex review-7), 2026-11-25. Not committed or pushed. No release.sh run.
**Status:** `python3 -I tests/test_corrections.py`: 24/24 pass (18 old + 6 new). test_presets, test_review3 pass. test_source_policy
(f1 "teal") and test_adversarial (repo policy governance) each fail 1 test, and they fail the same way in a HEAD worktree without my
files, so the cause is other agents' in-progress source-policy/policies edits, not this change.
**Decision to confirm:** `data/decisions/maintainers.yaml` = [shrestha-pranav] (new file). It is the documented exception to "no personal
data": public maintainer handles only. A c_corr_ ledger line whose `by` is not listed makes the import fail, the same as an agent `by`.
1. **P0 content-bound approval.** `corrections.claim_digest()` = sha256 of canonical claim content: claim id, entity + target, applies_to
   in order, key, value, kind, measurement, conditions, evidence type/urls/image hashes + transcriptions, source, terms/coi/submitter.
   sync time and issue state are left out. `review_corrections.decision_line` writes `digest` on every accept, and refuses a claim file
   with PII. `decisions.Decisions.claim_state`: a c_corr accept with a missing or stale digest -> `candidate` (withheld, preview shows it
   pending, stderr line). A reject stays a reject. The reviewer CLI and the queue treat a stale accept as undecided ("changed since accept").
   Real ledger: 0 c_corr lines (tested). No import.py hook needed (gate lives in decisions.py). `CR.apply` skips no-key/entity/value or PII files.
2. **P1 privacy before persistence.** `decoded()`/`has_pii()` catch literal, %-encoded (incl. %2540), HTML-entity and "(at)/(dot)" forms.
   `clean_url` drops userinfo and the fragment, plus token/identity query params (utm_*, token, sig, email, user, ...) and
   tokenish/PII values. It drops the whole URL when the host or path still carries PII. Payload ids must match the id pattern. A final
   `sanitize_doc` pass runs before write and dry-run print. The ledger `reason` is scrubbed and `evidence` is limited to the issue/proposal
   pointer. Test: issues #7/#8 inject PII in every field and URL part. No literal or encoded form reaches data/ or api/, #7 still publishes
   sanitized, and #8 (PII identity) never applies.
3. **P1 crawl policy per hop.** `policy_open()`/`PolicyRedirect` check the first URL and every redirect before the request is built. Allowed:
   the INTAKE exception (GitHub user-attachments, (private-)user-images, objects.githubusercontent.com, the asset S3 host; https only) or a
   *listed* `crawl: agent` source. human_only, none, unlisted and http are refused. `hash_image` uses it (sync binds the run's policy).
   Mocked tests: redirects to chargerlab (human_only), rtings (none), unlisted, the github issue page or http -> BlockedFetch, with zero
   requests to the destination. An agent source bouncing to human_only is also blocked. The exception is documented in the corrections.py
   docstring and in ARCHITECTURE.md section 0 item 13.
4. **Presets.** `_verdict`: a filtered key whose headline matches but has a different-valued alternative -> disagree (D10: never matched
   silently, even on the same side). No headline but alternatives -> disagree, or no when every value fails. Index `s[k]=="conflicted"` ->
   disagree, not unknown. Counts are now disjoint: `unknown`, `disagree`, `ruled_out` added, and `maybe` = unknown+disagree is kept for app.js
   (asserts sum == total, sum(by_kind) == known). Numbers before -> after (docs/api/v1 snapshot): matches and maybe unchanged for all 8 presets. Only ssd-dram-2tb changes: disagree 0 -> 15
   (unknown 49), because 15 conflicted rows used to be generic unknown.
5. **Measurement scope.** `independent_samples()`: URLs count once per site (www stripped) and photos once per distinct hash. The
   single_design_url must be a `kind: maker` domain for every evidence type, E4 included. Tested.
**Shared-file changes:** scripts/decisions.py (+~25: maintainers check and digest gate, lazy `import corrections`). New
data/decisions/maintainers.yaml. ARCHITECTURE.md item 13 (+6 lines). Owned files: corrections.py, review_corrections.py, presets.py,
tests/test_corrections.py. import.py untouched.
**Open / follow-ups:**
- A4: app.js `disagrees()` should mirror the new same-side and conflicted rules. The 15 SSD rows are counted right, but row tags read
  "Unknown value" instead of "Sources disagree". The smoke check `lenient-strict == maybe` still holds because maybe is unchanged.
- The issue form's blanket no-personal-data line (.github/ISSUE_TEMPLATE/field-correction.yml:13) should mention that maintainer handles
  are public. A4/A5 own that wording.
- Import does not rerun full `check()` (structural + PII + digest gates only); the CLI requires a clean check before an accept.
