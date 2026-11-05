# Documentation map

Portfolio readers: [project pitch, architecture, demos, CV and evidence index](18_PORTFOLIO.md).
This M09 package explicitly distinguishes verified scope from deferred recovery/load work.

Start here: [actual checkpoint](STATUS.md), then the selected milestone in
[the plan](04_PLAN.md). M08B daily operation has one supported primary path:
[live-up + manual generate](../tools/s02_data/README.md), configured with
[CONFIG.md](../tools/s02_data/CONFIG.md). Its current architecture is
[16_M08_LIVE_LOCAL.md](16_M08_LIVE_LOCAL.md).

M08C recovery work: [contract/runbook](17_M08C_RECOVERY.md) and
[explicit executable/pending case inventory](../test_support/m08c_cases.json).
Case PASS does not imply the whole M08C matrix passed.

Temporary owner-requested Vietnamese audit of all M08 work, schemas, generator
rules and current gaps: [M08 review document](TAM_THOI_M08_GIAI_TRINH_VI.md).
This is a review aid, not a new approved implementation contract.

Historical design and regression references (not extra daily setup steps):
[12: RAM campaigns](12_M08B_CONTINUOUS.md),
[13: generation/diversity](13_S02_GENERATION.md),
[14: immutable temporal storage](14_S02_TEMPORAL_SOURCE.md),
[15: selected-dataset replay](15_S02_LOCAL_WORKFLOW.md).
Their implemented utilities/tests remain for reproducibility. Current live
behavior takes precedence where older setup/activation instructions differ.

Original source snapshot: 2026-10-24; local documentation review: 2026-10-30
(Asia/Bangkok). Read STATUS before choosing a task; dated exports are historical.

| File | Responsibility | When to read |
| --- | --- | --- |
| [01_BUSINESS.md](01_BUSINESS.md) | Business purpose, outputs, proposed report definitions and exclusions | Before changing output meaning |
| [02_SOURCE_CONTRACTS.md](02_SOURCE_CONTRACTS.md) | Source overview, S01 tables/timeline, approved interface and recovery rules | Before source acquisition or semantic changes |
| [contracts/README.md](contracts/README.md) | Dated field-level source schemas/rules exported from the workbook | Before implementing a source adapter/simulator |
| [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | Proposed ownership, sequences, raw/ops/current/history/mart table map and publication | Before storage/transformation/orchestration work |
| [04_PLAN.md](04_PLAN.md) | M00–M09 deliverables, including gated M08A–D stabilization | Read only the current milestone and relevant dependencies |
| [06_AUTOMATION.md](06_AUTOMATION.md) | Clock modes, polling windows, shared-build serialization, scheduled-operation acceptance | Before implementing M05B/M06 jobs or claiming automatic operation |
| [07_M06_READINESS.md](07_M06_READINESS.md) | Etsy implementation gates and lease/retry/security acceptance checklist | Reviewing M06; actual runtime evidence remains in STATUS |
| [08_M07_REPORTING.md](08_M07_REPORTING.md) | Final report-view, filter, refresh and acceptance contracts | Before M07 DDL/UI changes |
| [09_M07_SCALE_MONITORING.md](09_M07_SCALE_MONITORING.md) | Bounded query/pagination, telemetry and multi-channel monitoring revision | Current M07 implementation contract |
| [10_S02_TEST_STRATEGY.md](10_S02_TEST_STRATEGY.md) | Isolated S02 environment, generator/oracle boundaries, fault matrix, load protocol and M08A–D gates | Before implementing any M08 part; planned, not runtime evidence |
| [11_M08A_ISOLATION.md](11_M08A_ISOLATION.md) | Finalized M08A identity/config/mount/resource guards and bounded cold-baseline contract | Before running the M08A harness; acceptance status remains in STATUS |
| [12_M08B_CONTINUOUS.md](12_M08B_CONTINUOUS.md) | Historical finite source/control/ledger regression contract | Reproducing older B campaigns, not daily setup |
| [16_M08_LIVE_LOCAL.md](16_M08_LIVE_LOCAL.md) | Current single-stack live admission, APIs, source worker and scheduling | Current M08B architecture |
| [17_M08C_RECOVERY.md](17_M08C_RECOVERY.md) | Scoped fault runner, case evidence and operator outcomes | Declared local matrix verified; assertion boundaries and rerun requirements |
| [STATUS.md](STATUS.md) | Actual completed work, checks, blockers, next task | Every coding session |
| [CODEX_VSCODE.md](CODEX_VSCODE.md) | Setup, first task prompt, review and Git workflow | Initial IDE setup and resuming work |
| [PROVENANCE.md](PROVENANCE.md) | Source links/revision and synchronization rules | Refreshing the coding contract |

The Google Doc and workbook remain review surfaces. These local files make the reviewed context usable offline in the editor. There is no automatic Google ↔ Git sync. Proposed technical/reporting sections remain DRAFT until accepted. Executable migrations/dbt contracts/tests must agree with the approved business/source semantics.

The completed M01 [target-column dictionary](05_TARGET_SCHEMA.md) defines the
warehouse/operational schema used by M03 dbt candidates and stable publication.
Source-schema CSVs remain source-facing contracts.

Current implementation includes M05A CLI/runtime acceptance and M05B periodic
website/eBay polling, alongside the preserved manual M04 website DAG. See
[polling operation](../orchestration/POLLING.md) and STATUS for scheduler/recovery
evidence and unrun checks. M06 local Etsy operation is in
[the Etsy guide](../orchestration/ETSY.md); M06 is committed locally. M07 operation
and review are in [the report guide](../reports/README.md).
Other operating instructions are
in `infra/README.md`, `orchestration/README.md` and `simulator/README.md`.
