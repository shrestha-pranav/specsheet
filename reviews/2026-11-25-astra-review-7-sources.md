Top three fixes, ranked:

1. **P0: Bind approval to correction content.** IDs depend on issue number and ordinal, while sync overwrites content; ledger entries contain no content digest (`scripts/corrections.py:87`, `:505`; `scripts/review_corrections.py:53`). An edit can reuse historical approval. **Exit:** edited values, evidence or target ordering remain withheld until freshly approved; import runs full validation.

2. **P1: Validate privacy before writing.** Payload fields and evidence URLs reach disk unsanitized (`scripts/corrections.py:418`, `:442`, `:505`). Reviewer handles and unsanitized reasons enter the ledger (`scripts/review_corrections.py:53`). **Exit:** inject literal/encoded PII across all fields and URLs; none reaches data or API artifacts. Explicitly resolve the reviewer-identity exception.

3. **P1: Enforce crawl policy on every redirect.** Attachment hashing uses unrestricted `urlopen`; a redirect to a human-only domain lacks a policy check (`scripts/corrections.py:396`). **Exit:** mocked redirects to human_only/none destinations send zero requests there; document the GitHub issue-intake exception.

Other findings:

- **Publication:** pending/rejected corrections have fixtures, but edited-after-accept does not (`tests/test_corrections.py:258`, `:293`). Non-correction measurement publication remains unverified within the allowed files.
- **TÜV:** exact certification matching is reported, not independently verified (`team/reports/2026-11-25-a2-independent-sources.md:12`). Require wrong-model, mixed-model and wrong-certification fixtures before sign-off.
- **Presets:** disagreements on the same side of a filter remain matches; conflicts without headline values become generic unknowns (`scripts/presets.py:59`, `:72`). Preserve explicit conflict state.
- **Counting:** headline fill counts once per row; `disagree` is already included in `maybe`, so adding them double counts (`scripts/presets.py:138`, `:187`).
- **Measurement scope:** distinct URLs do not prove independent samples; E4 single-design URLs evade maker-kind validation (`scripts/corrections.py:253`, `:275`).

Static review only; tests were not executed.
tokens used
80,545
Could not write [the review file](/home/pranavsh/projects/specsheet/reviews/2026-11-25-astra-review-7-sources.md): the read-only filesystem required escalation, and the approval request failed.

Top three fixes, ranked:

1. **P0: Bind approval to correction content.** IDs depend on issue number and ordinal, while sync overwrites content; ledger entries contain no content digest (`scripts/corrections.py:87`, `:505`; `scripts/review_corrections.py:53`). An edit can reuse historical approval. **Exit:** edited values, evidence or target ordering remain withheld until freshly approved; import runs full validation.

2. **P1: Validate privacy before writing.** Payload fields and evidence URLs reach disk unsanitized (`scripts/corrections.py:418`, `:442`, `:505`). Reviewer handles and unsanitized reasons enter the ledger (`scripts/review_corrections.py:53`). **Exit:** inject literal/encoded PII across all fields and URLs; none reaches data or API artifacts. Explicitly resolve the reviewer-identity exception.

3. **P1: Enforce crawl policy on every redirect.** Attachment hashing uses unrestricted `urlopen`; a redirect to a human-only domain lacks a policy check (`scripts/corrections.py:396`). **Exit:** mocked redirects to human_only/none destinations send zero requests there; document the GitHub issue-intake exception.

Other findings:

- **Publication:** pending/rejected corrections have fixtures, but edited-after-accept does not (`tests/test_corrections.py:258`, `:293`). Non-correction measurement publication remains unverified within the allowed files.
- **TÜV:** exact certification matching is reported, not independently verified (`team/reports/2026-11-25-a2-independent-sources.md:12`). Require wrong-model, mixed-model and wrong-certification fixtures before sign-off.
- **Presets:** disagreements on the same side of a filter remain matches; conflicts without headline values become generic unknowns (`scripts/presets.py:59`, `:72`). Preserve explicit conflict state.
- **Counting:** headline fill counts once per row; `disagree` is already included in `maybe`, so adding them double counts (`scripts/presets.py:138`, `:187`).
- **Measurement scope:** distinct URLs do not prove independent samples; E4 single-design URLs evade maker-kind validation (`scripts/corrections.py:253`, `:275`).

Static review only; tests were not executed.
done
   147	        (d / "snapshots.jsonl").write_text("".join(json.dumps(x) + "\n" for x in log))
   148	        cls.pol = SP.load(t / "data" / "source-policy.yaml")
   149	        cls.data = t / "data"
   150	        # dry run first: prints, writes nothing
   151	        buf = io.StringIO()
   152	        r = CR.sync(REPO, cls.data, dry_run=True, issues=ISSUES, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=buf, pol=cls.pol)
   153	        cls.dry_written, cls.dry_out = r["written"], buf.getvalue()
   154	        cls.dry_dir_exists = (cls.data / "corrections").exists()
   155	        CR.sync(REPO, cls.data, issues=ISSUES, hasher=fake_hash, now="2026-11-25T12:00:00Z", out=io.StringIO(), pol=cls.pol)
   156	        cls.imp0 = run_build(t)        # ids exist now (registry), no decisions yet
   157	        cls.checks = {p.name: bad for p, _, bad in CR.check_all(cls.data, cls.pol)}
   158	        cls.pre = {e: detail(t, e) for e in ("widgetco-w-100", "widgetco-w-200")}
   159	        cls.pre_prev = detail(t, "widgetco-w-200", preview=True)
   160	        lines = [RC.decision_line(cid, "accept_claim", "owner-handle", r, f"https://github.com/{REPO}/issues/{n}", at="2026-11-25T12:30:00Z", data_dir=cls.data)
   161	                 for cid, n, r in (("c_corr_1_1", 1, "E1 label photo, model visible"), ("c_corr_2_1", 2, "E3 ChargerLAB review"), ("c_corr_3_1", 3, "E2 maker datasheet"))]
   162	        RC.append(lines, cls.data)
   163	        cls.imp1 = run_build(t)
   164	        cls.b1 = {e: detail(t, e) for e in ("widgetco-w-100", "widgetco-w-200")}
   165	        cls.b1_prev = detail(t, "widgetco-w-200", preview=True)
   166	        cls.rows1 = {r["id"]: r for r in json.loads((t / "api" / "widgets" / "index.json").read_text())}
   167	        cls.trusted_text = "".join(p.read_text() for p in (t / "api" / "widgets").rglob("*.json"))
   168	        RC.append([RC.decision_line("c_corr_1_1", "reject_claim", "owner-handle", "photo shows a different revision", "https://github.com/x/y/issues/1",
   169	                                    at="2026-11-25T13:00:00Z", data_dir=cls.data)], cls.data)
   170	        run_build(t)
   171	        cls.b2 = detail(t, "widgetco-w-100")

exec
/bin/bash -lc "cat > reviews/2026-11-25-astra-review-7-sources.md <<'EOF'
# Astra review 7 — sources (2026-11-25)
Scope: static review of the requested files; no tests executed. Publisher, decision engine, TÜV adapter and crawler implementations were outside the read allowlist; their end-to-end guarantees remain unverified.

1. **P0 — Bind human approval to immutable correction content.**
Claim IDs contain only issue/proposal number and target ordinal ("'`scripts/corrections.py:87`); sync overwrites changed issue content (`scripts/corrections.py:496`, `scripts/corrections.py:505`).
Ledger lines bind only that ID, not the value, evidence or target (`scripts/review_corrections.py:53`); review skips already-decided IDs (`scripts/review_corrections.py:125`).
Thus an edited value or reordered `applies_to` reuses an old approval; import attaches the new content under that ID (`scripts/corrections.py:336`). This is an approval-reuse risk, not proof of publication without any historical ledger line.
Import also bypasses full `check()` (`scripts/corrections.py:321`): evidence, PII, agent restrictions and revision safeguards are not enforced there.
**Exit:** content digest includes entity, key, value, conditions, evidence hashes/URLs, method and scope; every change requires fresh approval; import/release reruns full validation. Accept → edit value/evidence/reorder targets → rebuild must withhold changed claims until a new human decision.
Human identity is also self-asserted: a TTY and non-agent-looking handle are not authentication (`scripts/review_corrections.py:32`, `scripts/review_corrections.py:219`). Enforce reviewer authorization at the ledger merge boundary.

2. **P1 — Enforce privacy before persistence, including URLs and ledger text.**
Sync copies evidence URLs and payload entity/key/build verbatim (`scripts/corrections.py:418`, `scripts/corrections.py:435`, `scripts/corrections.py:442`), then writes without `check()` (`scripts/corrections.py:505`). An email in a URL query or payload therefore reaches `data/` before validation.
The reviewer handle and unsanitized reason are deliberately stored in the public ledger (`scripts/review_corrections.py:53`, `scripts/review_corrections.py:65`), contradicting the blanket form promise (`.github/ISSUE_TEMPLATE/field-correction.yml:13`).
The PII detector only recognizes literal emails/@mentions (`scripts/corrections.py:193`); encoded emails and profile-path handles escape it. Source URLs flow unchanged into imported sources (`scripts/corrections.py:115`, `scripts/corrections.py:334`), so API exposure is a credible downstream risk, not verified here.
**Exit:** validate an allowlisted schema before any write; reject identifying URL components after decoding; scrub/reject ledger reasons; use non-personal reviewer identifiers or explicitly document the reviewer exception. Fixtures inject PII in every input field and URL component, then assert absence from data and published artifacts. Current test checks only two sentinel strings (`tests/test_corrections.py:195`).

3. **P1 — Put crawl enforcement at every network boundary and redirect hop.**
Attachment hashing calls unrestricted `urlopen` without `Policy.crawl` or redirect checks (`scripts/corrections.py:396`); sync invokes it for matched GitHub image links (`scripts/corrections.py:424`). A redirect to a human-only host would be followed without policy evaluation.
The policy marks ChargerLAB/Tom'"'s Hardware/TechPowerUp human-only ("'`data/source-policy.yaml:140`); `Policy.crawl()` is only a lookup (`scripts/source_policy.py:270`). The report'"'s Net.get guard does not establish coverage of this separate downloader ("'`team/reports/2026-11-25-a2-independent-sources.md:11`).
GitHub issue paths themselves are human-only (`data/source-policy.yaml:159`), while sync intentionally reads their API equivalent (`scripts/corrections.py:386`): define an explicit issue-intake exception instead of relying on the API hostname/path escaping policy.
**Exit:** shared fetch wrapper checks initial URL and every redirect before sending a request; mocked redirects to human_only/none hosts produce zero requests there. Cover attachment sync, dry-run sync and crawler requests; document the narrowly scoped GitHub intake exception.

Other requested checks:
- **Publication:** pending-correction exclusion and later rejection have fixtures (`tests/test_corrections.py:258`, `tests/test_corrections.py:293`), but no edited-after-accept fixture. Non-correction measured publication without a human ledger line cannot be established from these files; the Notebookcheck parser is reportedly unregistered (`team/reports/2026-11-25-a2-independent-sources.md:16`).
- **TÜV scope:** the report claims exact Eye Comfort 5-star matching and rejects lower/unstarred/2.0/Gaming/Color marks (`team/reports/2026-11-25-a2-independent-sources.md:12`). Wrong-certificate/model exclusion is unverified without the adapter and rule. Require fixtures with another model'"'s certificate, mixed-model pages, wrong certification programs and absent model binding before sign-off; preserve rule ID and certificate basis per "'`product/decisions.md:403`.
- **Preset conflicts can disappear:** `_verdict` flags disagreement only when alternatives cross a filter boundary (`scripts/presets.py:61`); differing values on the same side remain matches, narrower than D10'"'s disagreeing-alternative rule ("'`product/decisions.md:410`). With no headline value, it returns unknown and ignores alternatives, hiding conflict inside generic might-match (`scripts/presets.py:59`, `scripts/presets.py:72`). Require explicit conflict state independent of filter outcome and fixtures for both cases.
- **Counts:** per-kind fill counts each row'"'s headline once ("'`scripts/presets.py:138`); alternatives do not double count. `disagree` is a subset of `maybe`, not an additional bucket (`scripts/presets.py:187`); consumers must not add both. Require `sum(by_kind) == known` and disjoint displayed match/unknown/conflict totals.
- **Measured scope:** URL count is not independent sample count (`scripts/corrections.py:275`); E4 single-design URLs skip the maker-kind restriction (`scripts/corrections.py:253`). Require explicit sample identities and maker validation for E4 too; duplicate photos or URL variants must not satisfy the family guard.
EOF' in /home/pranavsh/projects/specsheet
2026-11-25T19:04:50.141666Z ERROR codex_app_server::bespoke_event_handling: request failed with client error: JSONRPCErrorError { code: -32000, data: None, message: "command execution approval is not supported in exec mode for thread `01a21417-bf0b-7851-b903-1fd0b10f4cea`" }
 exited 1:
2026-11-25T19:04:50.142156Z ERROR codex_core::tools::router: error=exec_command failed: CreateProcess { message: "Rejected(\"approval request failed\")" }
codex
Could not write [the review file](/home/pranavsh/projects/specsheet/reviews/2026-11-25-astra-review-7-sources.md): the read-only filesystem required escalation, and the approval request failed.

