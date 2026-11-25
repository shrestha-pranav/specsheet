# SSD DRAM seed list for the corrections flow (A2, 2026-11-25)

Brief: team/briefs/pm-2026-11-25-independent-sources-a2.md (#3b). Gate key `hw.dram_type`, preset ssd-dram-2tb, D8 in-scope rows
(maker source, not discontinued, `if.protocol: nvme` known) whose DRAM type is unknown in docs/api/v1 on 2026-11-25.
**Entity ids only, no values.** A person cites the fact (D9.2 evidence E1-E4); agents fetch none of the measurement sites.
Revision guard (D10): a family-wide claim needs two independent samples or one sample plus a maker single-design statement.
TechPowerUp `/ssd-specs/` links are rejected (D9: excluded; the policy gate matches hosts only, so techpowerup.com is human_only for reviews).

| family | rows | entity ids |
|--|--|--|
| WD_BLACK SN850X | 8 | western-digital-wds100t2x0e, western-digital-wds100t2xhe, western-digital-wds200t2x0e, western-digital-wds200t2xhe, western-digital-wds400t2x0e, western-digital-wds400t2xhe, western-digital-wds800t2x0e, western-digital-wds800t2xhe |
| Kingston NV3 | 7 | kingston-snv3s-1000g, kingston-snv3s-2000g, kingston-snv3s-4000g, kingston-snv3s-500g, kingston-snv3sm3-1t0, kingston-snv3sm3-2t0, kingston-snv3sm3-500g |
| Kingston NV2 (SNV2S; controller/NAND swaps known: cite per revision) | 5 | kingston-snv2s-1000g, kingston-snv2s-2000g, kingston-snv2s-250g, kingston-snv2s-4000g, kingston-snv2s-500g |
| WD Red SN700 | 5 | western-digital-wds100t1r0c, western-digital-wds200t1r0c, western-digital-wds250g1r0c, western-digital-wds400t1r0c, western-digital-wds500g1r0c |
| WD PC SN810 (OEM) | 4 | western-digital-sdcpnry, western-digital-sdcpnrz, western-digital-sdcqnry, western-digital-sdcqnrz |
| SanDisk PC SN5000S (OEM) | 4 | western-digital-sdepnsj, western-digital-sdeptsj, western-digital-sdeqnsj, western-digital-sdeqtsj |
| WD Blue SN5000 | 4 | western-digital-wds100t4b0e, western-digital-wds200t4b0e, western-digital-wds400t4b0e, western-digital-wds500g4b0e |
| SanDisk PC SN5100S (OEM) | 4 | western-digital-sdfpnsm, western-digital-sdfptsm, western-digital-sdfqnsm, western-digital-sdfqtsm |
| WD Blue / SanDisk SN5100 | 4 | western-digital-wds100t5b0e-00cpe0, western-digital-wds200t5b0e-00cpe0, western-digital-wds400t5b0e-00cpe0, western-digital-wds500g5b0e-00cpe0 |
| SanDisk PC SN8000S (OEM) | 4 | western-digital-sdepnrg, western-digital-sdepnrk, western-digital-sdeqnrg, western-digital-sdeqnrk |
| WD_BLACK SN850P (PS5) | 4 | western-digital-wdbbyv0010bnc-jrsn, western-digital-wdbbyv0020bnc-jrsn, western-digital-wdbbyv0040bnc-jrsn, western-digital-wdbbyv0080bnc-jrsn |
| WD Green SN3000 | 3 | western-digital-wds100t4g0e-00cps0, western-digital-wds200t4g0e-00cps0, western-digital-wds500g5g0e-00vnf0 |
| WD Green SN350 | 3 | western-digital-wds200t3g0c, western-digital-wds250g2g0c, western-digital-wds500g2g0c |
| WD_BLACK SN770M | 3 | western-digital-wdbdnh0010bbk-wrsn, western-digital-wdbdnh0020bbk-wrsn, western-digital-wdbdnh5000abk-wrsn |
| Kingston A2000 | 3 | kingston-sa2000m8-1000g, kingston-sa2000m8-250g, kingston-sa2000m8-500g |
| Kingston NV1 (SNVS) | 4 | kingston-snvs-1000g, kingston-snvs-2000g, kingston-snvs-250g, kingston-snvs-500g |
| SanDisk SSD Plus NVMe | 4 | western-digital-sdssda3n-1t00-g26, western-digital-sdssda3n-250g-g26, western-digital-sdssda3n-2t00-g26, western-digital-sdssda3n-500g-g26 |
| Samsung 980 PRO | 1 | samsung-mz-v8p1t0b-am |

Total: 74 rows. Not listed: 40 portables with `if.protocol` unknown (Thunderbolt/USB4/connector-only cells, ruling 4 keeps them unknown;
they need an A1 ruling, not a DRAM fact). Note: Kingston NV1/NV2 rows carry a broken display name ('kingston.com/ssd 250GB'), a parser issue for A2.
