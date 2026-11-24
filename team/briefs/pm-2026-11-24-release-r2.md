# Brief: release promotion, rollback and private R2 archive (PM D2, D7; rewritten PM round 3, 2026-11-24). Owner: A3 (Opus).
**Changed 2026-11-24 (R3):** item 1 (licensing gate) moved to `pm-2026-11-24-licensing-gate.md`; do that first.
R2 is no longer a live origin at L1 and there is no bucket lock (takedowns must be possible). The release must be
pinned end to end. Read common.md, decisions.md D2 + D7, product/takedown-runbook.md, scripts/release.sh.
1. **Manifest before promotion.** The build writes the release manifest with per-file sha256 + byte counts, record
   and value counts per category and tier, `policy_version` + `policy_sha256` (licensing gate) and the git commit.
   `release.sh` verifies the built tree against it (file count, checksums, no unlisted domains with `RELEASE=1`,
   `policy_version` equals the one in git `main`) and refuses to publish on any mismatch.
2. **Promotion order.** Verify → publish gh-pages → build the Worker free query pack for the **same release id**
   (`build_r2.py --tier free`, api-gateway brief) → print the owner/coordinator deploy command. Never auto-deploy.
   Record `releases/<id>.json` (exists today) with the pack checksum, so `/health` can be checked against it.
3. **Rollback.** `scripts/rollback.sh <release_id>` (dry-run by default): republish gh-pages from the archived release
   (local `releases/` + archive) and print `wrangler rollback` / `wrangler deploy` for the matching pack. Test it
   locally against a temp gh-pages clone (`git worktree`), never the real remote.
4. **Private archive (after the owner creates R2; dry-run until then).** Upload the free tree, the query pack and the
   paid export to `specsheet-data/releases/<id>/`. Write-once is enforced by the script (refuse if the prefix exists),
   not by a bucket lock. Then write `current.json` {release, built_at, previous, policy_version}, which is used only by
   tooling, not by clients. rclone with an in-project RCLONE_CONFIG, creds from `pass specsheet/r2-release` via a
   chmod-600 file. Skip with a clear log line when creds are absent. `RELEASE_DRY_RUN=1` prints the plan. Keep the
   last 30 releases plus the first release of each month, and prune others (dry-run lists them).
5. **Changes feed** computed per tier from the previous release's gated output (archive or local `releases/`), not
   from state/r2-snapshots alone. Withheld values appear as `withdrawn` with no previous value (licensing-gate F10).
6. **Takedown support.** `scripts/purge_archived.py --domain D [--keys k1,k2]` (dry-run default): lists, and with
   `--apply` rewrites, affected archived releases (value → not_published, manifest note `purged: TD-...`), and
   deletes that domain's raw snapshots from the local backup and R2 `specsheet-raw` including noncurrent versions.
   It is used in the runbook §2.6 drill.
7. Raw backup bucket: versioning + 30-day noncurrent expiry. Honour per-source retention caps (e.g. 72 h) in the
   backup copy too.
Never run release.sh without RELEASE_DRY_RUN=1. No commits. Report team/reports/2026-11-24-a3-release-r2.md (<=60 lines),
listing shared-file edits.
