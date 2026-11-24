# Takedown and correction runbook (D7, PM round 3, 2026-11-24)

Who: the coordinator runs it and the owner answers mail. Nothing here needs counsel, except a request that
threatens legal action. Forward that to the owner the same day and do nothing irreversible until they reply.
Public log: `team/queue/takedowns.md`, one line per case: date, ticket id, source domain, scope, action,
policy_version, release id. **No requester names, emails or message text in the repo** (it is public). Those stay in
the owner's mailbox.

## 1. Intake (day 0)
Channels: `legal@` (takedowns), `corrections@` and GitHub issues (corrections), `hello@` (anything else). Give each
case a ticket id `TD-YYYYMMDD-N` (takedown) or `CR-YYYYMMDD-N` (correction).
Classify it:
| Class | Example | Path |
|---|---|---|
| A. Rights-holder takedown | "remove our spec data", "our terms forbid reuse" | §2 |
| B. Factual correction | "this wattage is wrong" | §3 |
| C. Personal data | a name or email in a GitHub issue, in miss text, or in `team/queue/requests.md` | §4 |
| D. Trademark/logo | "you use our mark" | §2, scope = names/marks shown |
| E. Security | vulnerability report | GitHub private vulnerability reporting; not this runbook |

## 2. Takedown (class A/D)
1. **Acknowledge within 3 business days.** Use the reply template below. Ask for the specific pages, fields or
   values only if the request is unclear. Do not ask for proof of identity for a removal; removing is the safe side.
2. **Decide scope**, the narrowest that satisfies the request: one value, one field (spec key) for one source, or a
   whole source domain.
3. **Change policy first** (`data/source-policy.yaml`): bump `policy_version`, set `free: false` (and therefore
   paid/grant false) for the domain. Add evidence `{level: fetched, refs: ["takedown:TD-..."]}` and a changelog line.
   For field scope, add a `withhold_keys: [...]` entry on that domain (the gate supports it, see the licensing-gate
   brief). This is what stops the next build from bringing the value back.
4. **Rebuild and release** (coordinator): `scripts/release.sh`. The gate turns affected values into
   `not_published`. Check the release diff for the expected count and that nothing else moved.
5. **Live surfaces**, within 7 days of the valid request:
   - GH Pages: the release republishes gh-pages (orphan, one commit), and the old content goes after the Pages CDN
     refresh (~10 min). GitHub can still serve an unreachable old commit by SHA. If the requester insists, the owner
     asks GitHub Support to purge it.
   - Worker: deploy the new query pack (`wrangler deploy`, owner/coordinator). Cached responses are keyed by
     release id, so they expire with the old release.
   - Verify: `curl` one affected product on Pages and on the Worker, `/health` shows the new release and
     policy_version, and a search for the removed value finds nothing.
6. **Private copies**, within 14 days: delete affected objects in R2 `specsheet-data/releases/*`, or rewrite those
   releases with the value removed and record that in their manifest. Delete that source's snapshots from local
   `raw/`, the second-disk backup and R2 `specsheet-raw`, including noncurrent versions, if the request covers
   collection. Nothing is bucket-locked, so this is possible (D2).
7. **Close:** reply with what was removed and from which release. State plainly that copies others already made
   under the licence (forks, mirrors, downloaded bulk files) are outside our control. Log the case in
   `team/queue/takedowns.md`. If the source was a maker, add it to the crawler's do-not-crawl list too.

Reply template (acknowledge): "Thanks, we received your request about <source/page> on <date> (ref TD-...). We
publish only specification values with links to your pages, not your text or images. We will remove <scope> from
the site and API in the next release, within 7 days, and confirm when done."

## 3. Correction (class B)
1. Acknowledge within 3 business days. GitHub issues: reply on the issue.
2. Check the cited source. If the source states the corrected value, record a ledger decision (normal review
   flow) and release. If our value matches the source and the source is wrong, keep the value, add a note to the
   record, and suggest the reporter contact the maker. Never "fix" a value against its own cited source.
3. Close the issue with the release id. Corrections from the maker themselves can be accepted on their written
   statement as a source, with the email kept privately and cited as "maker correspondence, <date>".

## 4. Personal data (class C)
Same day: edit or delete the GitHub comment or issue (or ask GitHub), and remove the line from
`team/queue/requests.md`. Miss text in Analytics Engine cannot be deleted per point. Reply honestly: it holds no IP
or identifier linkable after 48 h, it ages out at the platform's retention, and it was redacted before writing.

## 5. Drill (before announce, checklist L1)
Add a fake domain `takedown-drill.invalid` to a test build with one value, run §2 steps 3-5 against a local build
and a `wrangler dev` Worker, and confirm the value disappears from records, indexes, facets, diffs and the query
pack. Time it. Record the result in `team/queue/takedowns.md` as `DRILL`.
