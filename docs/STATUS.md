# Actual project status

Updated: 2026-10-25 (Asia/Bangkok).

- Stage: M02 website acquisition implemented and runtime-checked; awaiting owner review before M03.
- Starting M02 Git state: `main` at `6c74517`, synchronized with `origin/main`. The pre-existing untracked root file `HANDOFF_SHA256SUMS.txt` was not changed. All M02 changes remain unstaged; no commit or remote push was performed.
- Approved and preserved: S01/source contracts, independent mapping version, observed-only history, source/account identity, amount grain/currency, and independent payment/fulfillment/cancellation state.
- M01 technical direction accepted by the owner: PostgreSQL 16.15 Bookworm, one instance/four databases, named-volume persistence, idempotent migrations, least-privilege service roles, candidate `build` schema, and stable report views.
- Git workflow updated by the owner on 2026-10-25: Codex leaves completed work unstaged for review; the owner normally stages, commits, and pushes. Codex performs Git write actions only when explicitly requested in the current task.
- Implemented: target field dictionary; Compose PostgreSQL bootstrap; database/role boundaries; raw/ops/config/core/mart/report schemas; migration ledger and rerun command; four-row approved S01 mapping seed; empty stable publication tables/views; repeatable M01 database acceptance SQL.
- Implemented through M02: the website source schema, fixed S01 source-state playback, consistent read-only website extraction, append-only raw acquisition evidence, run/checkpoint audit, interruption injection, replay evidence, and repeatable runtime acceptance runner.
- Not implemented: marketplace source services, dbt project/models/tests, Airflow installation/DAGs, publication command, dashboard, and full end-to-end recovery tests. Empty core/mart tables remain contracts/publication targets, not generated business results.

## M02 decisions

- The website source physical schema is the approved nine-table v0.1 contract: source IDs are `TEXT`, money is `NUMERIC(18,2)`, timestamps are `TIMESTAMPTZ`, and PK/FK/unique/local enum and amount bounds are database constraints. Cross-row order sums, currency, and shipment allocation are validated by playback before its single transaction commits.
- Simulator and acquisition boundaries are separate Docker images. Only `website-simulator` contains the allow-listed source-state fixtures and uses `website_writer`. `website-collector` contains no fixture tree, reads with `website_reader` in one `REPEATABLE READ READ ONLY` transaction, and appends platform evidence with `platform_ingest`.
- A raw record is committed before the checkpoint. A crash or injected failure after that commit leaves the exact raw bytes and a failed run but cannot advance the checkpoint. The checkpoint and successful run transition then commit together. Equal-window replay appends another auditable raw/run and may replace the checkpoint's successful run ID; an older window cannot regress its timestamp.
- The approved 120-second overlap is explicit in the S01 windows: 08:58–09:03, 09:01–09:11, and 09:09–09:15. Only the observed 09:01, 09:10, and 09:14 source versions are acquired; the unobserved 09:00 state is not fabricated.
- Python runtime is isolated in containers based on `python:3.12.12-slim-bookworm` pinned by digest. `psycopg`, its binary package, and `typing_extensions` are pinned to 3.3.6/3.3.6/4.16.0. The repository `.dockerignore` excludes `.env`, Git data, caches, runtime data, and build artifacts from Docker contexts.

## Exact M02 checks and outcomes

- Starting inspection: `main` at `6c74517` (`origin/main` at the same commit); only pre-existing `HANDOFF_SHA256SUMS.txt` was untracked. PostgreSQL was already running on host port 5433; raw/core/mart were initially empty and the four M01 mapping rows existed.
- `python -m py_compile simulator/website_playback.py ingestion/website.py` — PASS.
- PowerShell parser checks for `infra/scripts/migrate.ps1` and `infra/scripts/run_m02_s01.ps1` — PASS.
- `docker compose --env-file .env --file infra/compose.yaml config --quiet` — PASS, exit 0. The sandboxed attempt emitted an unreadable user Docker-config warning but configuration validation itself succeeded.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1` — PASS after correcting the source migration's initial overly broad `REVOKE`; the failing transaction rolled back before the corrected rerun. A later full rerun also passed with existing objects and data unchanged.
- From `fixtures/s01/`, `python verify.py` — PASS, all 10 offline checks; `python -m unittest -v test_tools.py` — PASS, 10 tests.
- `Get-Content tests/m01_acceptance.sql -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T postgres psql --set ON_ERROR_STOP=1 --username postgres --dbname data_platform` — PASS, `M01 database contract PASS`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m02_s01.ps1` — PASS on the final pinned build, execution ID `cfee55cf-703a-446a-ba40-0f12162efb08`. It built both images, applied states 0901/0910/0914, injected the expected post-raw failure, acquired all three scheduled windows, replayed the final window, checked role boundaries, and verified the collector image has neither `/fixtures` nor `/app/fixtures`.
- Final execution evidence query — PASS: `failure-test|FAILED|1`, `scheduled|SUCCEEDED|3`, and `replay|SUCCEEDED|1`. The successful scheduled payload states are exactly `NOT_REQUESTED`, `REQUESTED`, `CANCELED`; the checkpoint is `2026-10-17 09:15:00+00`, points to the successful replay run, and never points to the failed run.
- The first full runner attempt exposed a psql-variable substitution error inside a dollar-quoted acceptance block after runtime acquisition had completed. Passing the execution ID through a session setting fixed the assertion; subsequent isolated execution IDs passed. Earlier acquisition rows remain intentionally retained as append-only audit evidence.

## M02 checks not run / limits

- No clean-volume bootstrap was run during M02 because the task preserved the owner's existing local volume/data. The source migration was exercised through the documented idempotent migration path and the bootstrap script was updated for future empty-volume initialization.
- No dbt model/publication or Airflow DAG check was run; those begin in M03 and M04. Therefore M02 raw rows do not claim warehouse history/current/mart output, and core/mart remain empty.
- No invalid-source exception flow, concurrent source mutation stress test, or non-S01 shipment playback was added; M02 acceptance covers the approved fixed S01 states, interruption durability, replay audit, consistent read transaction, and enforced access boundaries.

## M01 decisions

- PostgreSQL is pinned to `postgres:16.15-bookworm`; host port defaults to 55432 because Windows rejected binding 5432 in the local check.
- UUIDs are supplied by writers; source IDs remain TEXT and account-scoped. Amounts use `NUMERIC(20,6)` plus currency, timestamps use `TIMESTAMPTZ`, and SHA-256 values require 32 bytes.
- Raw rows are append-only for `platform_ingest`. dbt's future `platform_transform` role can create candidate relations only in `build`; it cannot mutate stable core/marts. `platform_publisher` owns the later tested-release write path; `platform_report` can select only report views.
- The migration rerun policy is explicit and idempotent. Initial bootstrap scripts run only for an empty official-image volume; later runs use `infra/scripts/migrate.ps1`. No database reset is an upgrade mechanism.
- The four S01 mapping rows are seeded from `fixtures/s01/config/product_mapping.json`, not from golden warehouse outputs. Exact active listing/variant identities are unique; ambiguous SKU fallback remains a visible transformation exception rather than a guessed match.

## Exact M01 checks and outcomes

- Tool inspection: Python 3.12.7, Docker CLI/Engine 29.7.2, Docker Compose 5.5.0, Git available; host `psql`, dbt, and Airflow not on PATH. Docker access required running outside the filesystem sandbox.
- `docker compose --file infra/compose.yaml config --quiet` with process-only test variables — PASS.
- `C:\Program Files\Git\bin\bash.exe -n infra/postgres/bootstrap/00-bootstrap.sh` — PASS. The initial generic `bash -n` attempt selected WSL and failed with `E_ACCESSDENIED`; Git Bash provided the applicable syntax check.
- PowerShell parser over `infra/scripts/migrate.ps1` — PASS.
- From `fixtures/s01/`, `python verify.py` — PASS, all 10 offline fixture checks; `runtime_pipeline_tested` remains false.
- From `fixtures/s01/`, `python -m unittest -v test_tools.py` — PASS, 10 tests.
- Clean bootstrap: `docker compose --file infra/compose.yaml down --volumes`, then `docker compose --file infra/compose.yaml up --detach --wait`, using process-only test passwords — PASS; PostgreSQL 16.15 became healthy and all bootstrap migrations completed. The removed volume was the disposable task-created `multi-channel-order-platform_postgres_data`, verified by its Compose labels and empty business tables.
- `Get-Content tests/m01_acceptance.sql -Raw | docker compose --file infra/compose.yaml exec -T postgres psql --username postgres --dbname data_platform` — PASS, `M01 database contract PASS`. It verifies four databases, required relations/views, three migration ledger entries, four mappings, validated constraints, append-only raw, transform/publisher separation, report isolation, and marketplace/platform database isolation.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1` after bootstrap — PASS, exit 0; existing objects/seeds were unchanged. A first attempt without process-scoped bypass was blocked by the machine's script execution policy before running; documentation now gives the working command without changing machine policy.
- `docker compose --file infra/compose.yaml restart postgres`, wait healthy, then rerun `tests/m01_acceptance.sql` — PASS, proving named-volume restart persistence. The container was stopped afterward; the final local test volume remains and contains no runtime source/order data.
- Live TCP login as `platform_report` selected `report.orders_current` successfully (0 rows) and `SELECT` from `raw.raw_records` failed with `permission denied for schema raw` as required.

## Checks not run / limits

- No dbt or Airflow runtime check: neither tool is installed and their projects belong to later milestones.
- No source HTTP/database integration or pipeline behavior check: M02+ scope. PostgreSQL M01 storage/bootstrap did run; empty target tables do not claim transformation behavior.
- No external PostgreSQL client check because host `psql` is absent; all SQL checks ran with the pinned container's `psql` over both local socket and authenticated TCP where relevant.

## M01 follow-up — Compose environment resolution

- On 2026-10-25, an owner-run `infra/scripts/migrate.ps1` exposed that nested
  Compose calls did not automatically load the repository-root `.env` because
  the Compose file lives under `infra/`.
- The runner now resolves the root `.env` explicitly and passes it with
  `docker compose --env-file`; `-EnvFile` can override the path. The README uses
  the same explicit option for every direct Compose command.
- `docker compose --env-file .env --file infra/compose.yaml config --quiet` —
  PASS, exit 0.
- `powershell -NoProfile -ExecutionPolicy Bypass -File
  infra/scripts/migrate.ps1` without process-exported variables — PASS, exit 0.
- Piping `tests/m01_acceptance.sql` through Compose with the root env file —
  PASS, `M01 database contract PASS`. Existing volume/data was not deleted or
  reset.

## Next task

Owner review of the unstaged M02 changes. Then select M03 website dbt/release explicitly; do not start M03 automatically.

## Session update template

- Selected milestone / scope:
- Starting branch / commit:
- Files and behavior changed:
- Technical decisions and draft/approved status:
- Exact checks / results / not-run checks:
- Remaining issues and next task:
- Suggested owner commit message and files to review; Codex leaves changes unstaged unless explicitly asked otherwise.
