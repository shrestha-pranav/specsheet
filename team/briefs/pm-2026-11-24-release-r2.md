# Brief: one licensing gate + immutable R2 releases (PM D1.3, D2). Owner: A3 (Opus). Read common.md + decisions.md.
1. **Single gate for both tiers.** Move the source exclusion list from api-worker/licensing-exclusions.json to
   `data/source-policy.yaml` (or extend ARCHITECTURE §15.4 `data/sources.yaml`, your call; one file), fields per
   source domain: `republish_free: yes|facts_link_only|no`, `republish_paid: yes|no`, `basis`, `audit_ref`
   (research/data-licensing.md section). build.py (free) and build_r2.py (paid) both read it; a spec whose sources
   are all `no` for that tier is published as status `not_published` (existing status) with no value, never
   silently dropped. Default for unlisted domains: free=facts_link_only, paid=no (fail closed for paid).
   Seed from licensing-exclusions.json + research/data-licensing.md when it lands; do not edit that research file.
   Never publish expression (descriptions, images, PDFs) in either tier: add a test that record text fields are
   limited to names/identifiers/enums/numbers + notes we wrote.
2. **Immutable releases.** release.sh (after gh-pages publish succeeds) uploads docs/api/v1 + r2 artifacts to
   `specsheet-data/releases/<release_id>/` (write-once: refuse if prefix exists) then writes `current.json`
   {release, built_at, previous}. Tool: rclone with RCLONE_CONFIG in-project, creds from pass via chmod-600 file
   (`pass specsheet/r2-release`, created by owner). Skip with a clear log line when creds are absent. Dry-run mode
   honoured (RELEASE_DRY_RUN=1 prints the plan). Changes feed computed from the previous R2 release, not only
   state/r2-snapshots.
3. Licence headers in outputs: manifest.json gets `license: "ODbL-1.0"`, `license_url`, `attribution` text.
4. Keep shared-script edits minimal; build.py/release.sh edits listed in report. Never run release.sh without
   RELEASE_DRY_RUN=1. Tests in tests/. No commits. Report team/reports/2026-11-24-a3-release-r2.md (<=60 lines).
