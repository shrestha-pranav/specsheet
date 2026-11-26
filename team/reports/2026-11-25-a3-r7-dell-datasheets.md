# A3-docs r7: Dell monitor datasheets (flicker + USB-C), 2026-11-25
**Outcome: no fill. No Dell monitor document source can be fetched under our rules.** Preset no-pwm-usbc-monitor flk.pwm 376/494 (76.11%) before and after.
Bare `import.py --strict-parsers` rc 0 (parser_drift 0) and `build.py` rc 0, both under flock. release.sh not run. Nothing committed. No parser or policy change.

## Decisions / open questions (coordinator)
- **OPEN: the gate needs +20 flk.pwm.** Dell can't supply them through documents. Options: (a) accept 76.1% for now. (b) Ask the owner whether
  dl.dell.com /content/ can be used. It is robots-disallowed today, so the answer is no unless Dell changes it. (c) Get flicker from another
  official source (TÜV Rheinland certificate DB? not checked: ToS/robots unknown). (d) Re-scope the gate so rows from silent pages don't count against it.
- **source-policy.yaml not edited.** dl.dell.com is a Dell document host that isn't listed, but nothing on it is fetchable for these models (see below), so adding it would have no use.
- Third-party copies of Dell user guides (gzhls.at, manualslib, manua.ls) do state "Flicker-Free" for e.g. S2725QS. They are not maker sources and were not used.

## What was tried (7 GETs, crawler UA, 1 req/s, stopped at the first 403 on each host)
- Stored pages: the 89 dell-us-monitors snapshots link only one product PDF, a U3824DW sheet on www.delltechnologies.com/asset/.
  The others link only legal and SupportAssist pages. The "Product Safety, EMC and Environmental Datasheets" lines are regulatory and say nothing about flicker.
- www.delltechnologies.com /asset/ PDF: **403** (robots allows it). Blocked. Not retried.
- www.dell.com/support product docs and manuals pages: **403** on both URL shapes. Blocked.
- dl.dell.com robots: `Allow: /manuals, /topicspdf; Disallow: /`. Current guides are at /content/manualNNN-* (disallowed).
  The allowed /manuals monitor index (7603 links) lists only legacy models. Of the 41 Dell rows without flk.pwm, only P1917S appears there.
  Its guide is a 5-model family guide, and its only flicker line is shared prose. Row scope binds that to nobody, and prose is not read anyway.
- i.dell.com (search): only JP datasheets for older models (U2721DE, U2722D) and catalogs, which are marketing. No current US monitor sheets.
- Missing flk.pwm (41 Dell rows, the 28 in scope among them): AW2525HM AW2725D/DM/Q AW2726DL/DM AW3225DM AW3425DW E2026H E2225HM/HSM
  E2425HM/HSM P1425 P1917S P2425D/DE P2725D/DE/QE P3425WE S2725QC/QS S3225QC/QS S3425DW SE2225HM SE2426H/HGS SE2726H/HGS U2424H U2724D/DE
  U2725QE U3225QE U3425WE U3824DW U4025QW U4323QE U4924DW.

## Files
Edited: research/monitors/merchants.md (+r7 section: hosts recorded as blocked / robots-disallowed). New: this report.
Shared files: none. Not touched: _docspec*.py, docspec_r3.py, policies.yaml, source-policy.yaml. Nothing written to raw/ (probe PDFs are in /tmp/dellds).
