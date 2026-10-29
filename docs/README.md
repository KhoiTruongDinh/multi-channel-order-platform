# Documentation map

Original source snapshot: 2026-10-24; local documentation review: 2026-10-28
(Asia/Bangkok). Read STATUS before choosing a task; dated exports are historical.

| File | Responsibility | When to read |
| --- | --- | --- |
| [01_BUSINESS.md](01_BUSINESS.md) | Business purpose, outputs, proposed report definitions and exclusions | Before changing output meaning |
| [02_SOURCE_CONTRACTS.md](02_SOURCE_CONTRACTS.md) | Source overview, S01 tables/timeline, approved interface and recovery rules | Before source acquisition or semantic changes |
| [contracts/README.md](contracts/README.md) | Dated field-level source schemas/rules exported from the workbook | Before implementing a source adapter/simulator |
| [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | Proposed ownership, sequences, raw/ops/current/history/mart table map and publication | Before storage/transformation/orchestration work |
| [04_PLAN.md](04_PLAN.md) | M00–M08 deliverables, acceptance and milestone commits | Read only the current milestone and relevant dependencies |
| [06_AUTOMATION.md](06_AUTOMATION.md) | Clock modes, polling windows, shared-build serialization, scheduled-operation acceptance | Before implementing M05B/M06 jobs or claiming automatic operation |
| [07_M06_READINESS.md](07_M06_READINESS.md) | Etsy implementation gates and lease/retry/security acceptance checklist | Reviewing M06; actual runtime evidence remains in STATUS |
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
[the Etsy guide](../orchestration/ETSY.md); the implementation is unstaged for review.
Other operating instructions are
in `infra/README.md`, `orchestration/README.md` and `simulator/README.md`.
