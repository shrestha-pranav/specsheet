# Brief: SSD DRAM/HMB/NAND/controller from maker publications. Owner: A2-ssd. Read common.md, D9, team/reports/2026-11-25-a5-pm-round5.md (SSD section), research/ssds/ (profile, manufacturers).
SSD DRAM preset is 67.4% (gate 80%). Find maker-published statements (datasheets, product briefs, spec PDFs, support FAQ pages, press kits) for in-scope SSD configs lacking dram/hmb, across WD/SanDisk, Samsung, Solidigm, SK hynix, Teamgroup, Corsair, Seagate, Lexar, PNY, Silicon Power, Kingston (Kingston naming is being fixed by another agent; don't touch the Kingston adapter — only add doc/claim sources).
- Use only domains with crawl: agent; new maker domains: add to data/source-policy.yaml as kind maker (free true, paid false, licence_grant false, crawl agent, evidence checked today) and bump the policy version — you are the only agent editing source-policy.yaml this round; list each addition.
- Explicit statements only: "DRAM-less", "HMB", "DRAM cache: 1GB LPDDR4" etc. Never infer DRAM from controller model. Family-level statements bind only to configs listed by the maker under that family.
- New extractor, pending @N policy. Fixtures. Measure preset fill before/after.
- Blocked hosts (403/WAF/robots): record and move on. No workarounds.
Report: team/reports/2026-11-25-a2-ssd-dram.md (<=50 lines).
