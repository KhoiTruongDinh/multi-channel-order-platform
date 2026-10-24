# Documentation map

Snapshot date: 2026-10-24 (Asia/Bangkok). Read the current repository status before choosing a task.

| File | Responsibility | When to read |
| --- | --- | --- |
| [01_BUSINESS.md](01_BUSINESS.md) | Business purpose, outputs, proposed report definitions and exclusions | Before changing output meaning |
| [02_SOURCE_CONTRACTS.md](02_SOURCE_CONTRACTS.md) | Source overview, S01 tables/timeline, approved interface and recovery rules | Before source acquisition or semantic changes |
| [contracts/README.md](contracts/README.md) | Dated field-level source schemas/rules exported from the workbook | Before implementing a source adapter/simulator |
| [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | Proposed ownership, sequences, raw/ops/current/history/mart table map and publication | Before storage/transformation/orchestration work |
| [04_PLAN.md](04_PLAN.md) | M00–M08 deliverables, acceptance and milestone commits | Read only the current milestone and relevant dependencies |
| [STATUS.md](STATUS.md) | Actual completed work, checks, blockers, next task | Every coding session |
| [CODEX_VSCODE.md](CODEX_VSCODE.md) | Setup, first task prompt, review and Git workflow | Initial IDE setup and resuming work |
| [PROVENANCE.md](PROVENANCE.md) | Source links/revision and synchronization rules | Refreshing the coding contract |

The Google Doc and workbook remain review surfaces. These local files make the reviewed context usable offline in the editor. There is no automatic Google ↔ Git sync. Proposed technical/reporting sections remain DRAFT until accepted. Executable migrations/dbt contracts/tests must agree with the approved business/source semantics.

The full target-column dictionary is not included yet: M01 completes it before dependent migrations/models. Source-schema CSVs are not the warehouse schema.
