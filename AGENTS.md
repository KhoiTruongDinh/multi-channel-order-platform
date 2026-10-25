# Repository instructions

Build a reproducible local multi-channel order DE portfolio project. Work one named milestone at a time; do not generate the entire application in one task.

## Start each task

1. Read `docs/STATUS.md`, then the selected milestone in `docs/04_PLAN.md`.
2. Read the relevant business/source/architecture sections and source contract files listed in `docs/README.md`. Inspect the existing code and Git status before editing.
3. Treat approved S01/source behavior as fixed. dbt and Airflow are required. New architecture, report/tool and milestone details are proposals; resolve routine technical choices explicitly in the milestone, and ask only when changing material agreed behavior.

## Boundaries

- Python acquires data, verifies webhook bytes and maintains raw/operational state. dbt owns business SQL transformations. Airflow orchestrates reusable commands; the webhook receiver runs outside a DAG.
- Marketplace ingestion must use HTTP, with no access to simulator backing storage. Website access is read-only. No pipeline code may read `fixtures/s01/expected`, `source_states`, or the scenario truth ledger as its source interface.
- Test code may read golden expectations. Simulators may serve source-state fixtures, never expected warehouse outputs.
- Preserve every raw acquisition/delivery audit, deduplicate logical versions, and never fabricate unobserved snapshots. Keep payment, fulfillment and cancellation independent. Keep source/account-scoped identity and money grain/currency.
- Preserve source-version identity separately from mapping/transformation version. Existing fingerprint behavior is specified by the fixture utilities/tests; do not silently change it.

## Delivery loop

- Implement only the selected milestone and necessary prerequisites. Keep changes small and readable; explain significant choices to the owner in Vietnamese. Repository docs/comments remain English.
- Complete target column definitions/constraints before writing dependent migrations/models. Do not treat source-schema exports as a finished warehouse schema.
- Run the milestone's meaningful acceptance checks. Record exact commands and actual outcomes, including checks not run. Never label generated code as verified runtime behavior.
- Update `docs/STATUS.md` with progress, decisions, failures, evidence and the next task. Synchronize changed contract/architecture/plan files; dated Google exports do not update automatically.
- Inspect the diff and run `git diff --check` when a Git worktree exists. Leave task changes unstaged for owner review. Do not stage, commit, amend, squash, rebase, or push unless the owner explicitly requests that Git action in the current task. The owner normally reviews, stages, commits, and pushes. Do not claim completion with failing required checks.
- When the owner explicitly requests a Git action, include only task-owned files and report the resulting status/SHA. Do not overwrite user work or reset a database without confirming its disposable test scope.
- Do not commit credentials, local DB volumes, runtime raw/logs, caches or dbt build artifacts. Synthetic fixed fixture evidence is intentionally versioned.

## Currently executable checks

From `fixtures/s01/`, run `python verify.py` and `python -m unittest -v test_tools.py` using an available Python 3 executable. These are offline fixture/utility checks, not database/HTTP integration tests. Add and document runtime checks as milestones implement them.
