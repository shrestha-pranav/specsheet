# Open questions for the owner (only what genuinely needs you)

Q1. **Legal review scope** (revenue on hold). Bundle: the R3 licence boundaries (`DATA-LICENSE.md`: ODbL over the
    compilation + permission-evidenced values only, no grant over other values), whether showing uncleared sources'
    facts with links on the free site is acceptable (D1.3, risk accepted for now), contribution terms that would
    allow a future alternative licence, the free terms/privacy drafts, paid-tier terms, sales tax, DMCA agent
    designation, and operating-structure questions (no recommendation here).
    **Added 2026-11-25 (D9.2):** the corrections form's contributor checkbox (ODbL 1.0 + DbCL 1.0, photos stay the
    contributor's) and whether to add a relicensing clause. Default: ship the checkbox without the relicensing clause,
    with crowd values tagged `relicense: false`.
Q2. **Lenovo PSREF.** 109k of 207k published values (53%) come only from PSREF. They stay free as linked facts but
    are outside our licence grant and outside paid. Ask Lenovo for written permission? Without it, paid laptops are empty.
Q3. **Domain.** Confirm `knownspec.com` (fallback `plainspec.com`). L1 needs it for contact email only.
Q4. **Preview quotas.** OK to serve `/v1/query`, `/v1/changes` and MCP free at 60/min and 1,000/day per client
    (IPv4 /32, IPv6 /64), shared REST+MCP, with a 60k/day global breaker? Default: yes.
Q5. **Permission emails (optional, cheap).** Agents draft them, and you send from `legal@`: VESA (DisplayHDR list),
    CSA (DCL), CARB (certified list), and (added 2026-11-25) TÜV Rheinland, on reusing Certipedia certificate facts. Each yes moves a source to `licence_grant: true` and paid-eligible. Default: send
    after L1.
Q6. **$5/month Workers Paid**, only if the local load test shows query CPU above the Free plan's 10 ms. Default: no
    spend unless the test fails.
