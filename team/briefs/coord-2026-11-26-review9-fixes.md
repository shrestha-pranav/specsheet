# Brief: Codex review-9 fixes (live data affected). Owner: A3-fix. Read common.md, reviews/2026-11-26-astra-review-9.md (all findings + exit criteria).
FIRST: measure real impact on the published build — for each P1, count currently published claims that the fixed logic would drop/change (git worktree for old code). Put the counts at the top of the report.
1. P1 _docspec_tvports.py:44 / docspec_r7tv.py:98: no count without an independently complete port inventory for that model; partial prefixes emit nothing (incl. zero); shared guides never transfer to other linked models.
2. P1 pb_pps_r7.py:61/87 SFC-derived PPS: affirmative own-product OUTPUT statement only; negation, questions, input/recharge context, other-model mentions emit nothing.
3. P1 _powerstation.py:32 UPS: trailing bounds ("20 ms maximum", "or less"), ranges ("between 10 and 20"), lower bounds ("≥20") handled per exit criteria; unsupported qualifiers => nothing.
4. P2 _xports.py:226 Dell: connector-unknown USB entry => keep literal unresolved list (no structured usbc_list that implies completeness).
5. P2 import.py:388/405 naming: binding veto before textual match; capacity tokenizer handles "1,024GB".
6. P2 aoc_monitors.py:43: withhold absence-based native refresh unless evidence retained (AOC unpublished anyway).
Reissue affected policies @N+1 pending, retire old verbatim, re-pin. Fixtures = the review's counterexamples. Do not run release.sh; finish with bare import.py --strict-parsers + build.py under flock rc 0. Report team/reports/2026-11-26-a3-review9-fixes.md (<=35 lines).
