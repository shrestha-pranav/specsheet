# A1 power strips - spec profile (2026-11-22)

## Decisions
- Profile: research/power-strips/spec-profile.yaml, 60 specs (12 core, 25 important, 23 detail). Over the 30-50 target: detail tier can be cut if A3 wants.
- Core: kind (surge vs plain), UL 1449 listed, VPR per mode (L-N/L-G/N-G + derived worst), outlets count, cord length, max A/W, USB ports/total W, auto shut-off.
- VPR is the comparable surge number; joules kept as "important" but flagged unreliable (UL does not test it; same SKU shows different joules on one page; revisions change it).
- Identity: model number incl. cord-length/colour suffix; revision/hardware version and datasheet date tracked (ISOBAR6ULTRA 2350 J -> 3330 J; Kasa v1/v2).
- Listing facet is a body list (UL/ETL/CSA), not a bool: Kasa HS300 is ETL, still legit.

## Grounded on (real pages)
- Eaton ISOBAR6ULTRA PDF (richest: AWG 14, 12 A breaker, 1440 W, mm spacing, 330 V let-through, 5th ed, $50k).
- Belkin SRA009p12tt8 page (L-N 400 / L-G 500 / N-G 500, 3780 J, right-angle, CEW $300k; alt text says 3940 J).
- CyberPower CSB604 datasheet (500 V all modes, 900 J; web page said 1800 J).
- TP-Link HS300 datasheet (VPR 600 V Type 3, USB 5V 2.4A shared, ETL).

## Traps found in the data
- Eaton PDF contradicts itself: "UL 1449 3rd Edition" in features vs "5th Ed Rev 2021" in spec table; 97,000 A vs 135,000 A.
- Breaker 12 A on a "15 A" strip. Belkin CEW void if protection indicator off.
- No brand publishes MCOV for consumer strips; dimensions missing on Belkin.

## UL Product iQ
- Root 403s for plain fetch. Listing pages and productspec.ul.com XBYS.E# pages are indexed/public, give company, E#, model prefixes (wildcards), status, Type 3 mark, standard. No VPR/joules, no full SKU list. Useful only to verify a listing exists. Details in notes.md.

## Open questions
- APC/se.com is JS-rendered (needs browser/API); Amazon Basics, GE/Jasco, Anker, Furman, Panamax not fetched.
- Is Product iQ search usable with a free account and permitted by ToS? Not tested.
- Should plain strips and surge strips be one category or two? Currently one with type.kind.
- VPR stored as given even when only one mode published (flag modes_unspecified) - A3 to formalize.
