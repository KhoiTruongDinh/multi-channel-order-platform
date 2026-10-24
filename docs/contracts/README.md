# Approved source field/rule exports

Read from the companion workbook on 2026-10-24. These are selected source-facing contracts, not vendor private database schemas or the finished target warehouse DDL. Original explanatory values are preserved, including Vietnamese notes and historical status wording. Current tool requirements (dbt/Airflow) are in the architecture/status files.

| CSV | Scope | Data rows |
| --- | --- | --- |
| [13_WebsiteSchema.csv](13_WebsiteSchema.csv) | Website source schema v0.1 | APPROVED — 19 October 2026 | 71 |
| [14_WebsiteRules.csv](14_WebsiteRules.csv) | Website rules v0.1 | APPROVED — 19 October 2026 | 22 |
| [15_eBaySchema.csv](15_eBaySchema.csv) | eBay source contract v0.1 | APPROVED — 19 October 2026 | 55 |
| [16_eBayRules.csv](16_eBayRules.csv) | eBay rules v0.1 | APPROVED — 19 October 2026 | 21 |
| [17_EtsySchema.csv](17_EtsySchema.csv) | Etsy receipt + webhook contract v0.1 | APPROVED — 19 October 2026 | 75 |
| [18_EtsyRules.csv](18_EtsyRules.csv) | Etsy rules v0.1 | APPROVED — 19 October 2026 | 25 |

S01 timeline/expected behavior is in [02_SOURCE_CONTRACTS.md](../02_SOURCE_CONTRACTS.md); complete selected payload examples and test expectations are in `fixtures/s01/`. The production pipeline must not consume expected answers or simulator control state. M01 must create the target-column dictionary before dependent migrations/models.
