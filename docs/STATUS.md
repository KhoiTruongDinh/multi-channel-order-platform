# Actual project status

Updated: 2026-10-26 (Asia/Bangkok).

- Stage: M04 Airflow website workflow implemented and runtime-checked; awaiting owner review before M05.
- The owner explicitly approved and requested the M03 local commit: `ca2e23cd21b8155a2a20cab72e0ae5b802e902d8` (`feat: transform and publish website orders with dbt`). Only M03 files were staged/committed. Final observed refs: `main` and `origin/main` both point to that SHA; the agent did not push. M04 changes remain unstaged. The pre-existing untracked `HANDOFF_SHA256SUMS.txt` is unchanged.
- Approved and preserved: S01/source contracts, independent mapping version, observed-only history, source/account identity, amount grain/currency, and independent payment/fulfillment/cancellation state.
- M01 technical direction accepted by the owner: PostgreSQL 16.15 Bookworm, one instance/four databases, named-volume persistence, idempotent migrations, least-privilege service roles, candidate `build` schema, and stable report views.
- Git workflow updated by the owner on 2026-10-25: Codex leaves completed work unstaged for review; the owner normally stages, commits, and pushes. Codex performs Git write actions only when explicitly requested in the current task.
- Implemented: target field dictionary; Compose PostgreSQL bootstrap; database/role boundaries; raw/ops/config/core/mart/report schemas; migration ledger and rerun command; four-row approved S01 mapping seed; empty stable publication tables/views; repeatable M01 database acceptance SQL.
- Implemented through M02: the website source schema, fixed S01 source-state playback, consistent read-only website extraction, append-only raw acquisition evidence, run/checkpoint audit, interruption injection, replay evidence, and repeatable runtime acceptance runner.
- Implemented through M03: website dbt sources/staging, source-content fingerprint parity, scoped product mapping, distinct observed order/line history and raw evidence links, current tables, four marts, frozen raw manifests, per-batch dbt artifacts, guarded batch lifecycle and atomic stable publication. Published website data now exists in core/mart/report.
- Implemented through M04: pinned Airflow runtime, isolated metadata/project environments, bounded website DAG invoking reusable commands, deterministic workflow/batch identities, durable stage attempt budgets, failure audit/cleanup, real scheduler retry/restart checks, CLI/DAG business parity, and exhausted-budget protection after an actual task clear.
- Not implemented: marketplace source services/models, dashboard, generalized exception remediation, and the combined end-to-end recovery campaign.

## M04 decisions and review points

- The current branch, M03 diff, Git identity and existing checks were inspected before committing M03. M04 starts from `ca2e23c`; the only unrelated untracked file was `HANDOFF_SHA256SUMS.txt`. Existing target definitions/constraints were reviewed first. No new business columns, tables, or target migration were needed.
- Airflow is pinned to `apache/airflow:3.3.2-python3.12` by image digest. One local `standalone` development service starts scheduler/API/DAG processing with LocalExecutor, parallelism 2, one active DAG run/task, task timeout 5 minutes and DAG timeout 20 minutes. dbt/project packages use a separate virtualenv with the existing M03 dependency lock. This is a local portfolio deployment, not a production/scale claim.
- `website_orders` is manually triggered (`schedule=None`, catchup disabled) with explicit timezone-aware source-clock window/observation params. Defaults read final S01 state at 09:15; earlier M02 observations stay retained. The DAG receives no simulator-writer credentials, fixtures, marketplace database access, or Docker socket. It never rewinds/reset source state to construct earlier snapshots.
- The DAG calls the reusable stage controller: collect -> freeze -> build_and_test -> publish. It invokes the existing M02 collector, M03 batch commands, dbt build/tests and publisher, with no business transformation SQL in the DAG/controller. The same command supports a normal direct CLI run via `--stage all`.
- A deterministic RECOVER-stage `ops.pipeline_runs` parent with stream `website_workflow` represents one bounded workflow/replay cycle; child acquisition/transform/publish rows retain their own stages and receive Airflow DAG/run context. The explicit execution ID determines workflow, batch and task-attempt IDs. Parent-row locking plus existing attempt uniqueness allocates at most five durable attempts per stage across Airflow retries/clears. An interrupted RUNNING attempt is consumed, never reset.
- Successful stages are no-ops on re-entry; freeze reuses the committed manifest, build retries use its same raw IDs/versions, and publish re-entry recognizes a previously committed release. Four Airflow retries plus the initial attempt are allowed. The terminal failure watcher marks an active batch/workflow failed and remains a failing leaf. An exhausted budget exits with code 42, mapped to AirflowFailException, so clearing the task cannot allocate operation attempt 6.
- Logs, UI credentials and dbt artifacts are ignored runtime data. UI is bound to localhost:8080; username `admin` and generated password in `runtime/airflow/state/passwords.json`. Database/UI credentials are separate. Metadata URL is supplied via Airflow's `_CMD` option with URL-encoded credentials and no trailing newline. Full operating/recovery instructions: `orchestration/README.md`.

## Exact M04 checks and outcomes

- `python -m py_compile orchestration/website_workflow.py orchestration/dags/website_orders.py orchestration/metadata_url.py tests/m04_probe.py` — PASS. PowerShell parser over `infra/scripts/run_m04_s01.ps1` — PASS. `docker compose --env-file .env --file infra/compose.yaml config --quiet` — PASS.
- From `fixtures/s01/`, `python verify.py` — PASS, 10 offline checks; `python -m unittest -v test_tools.py` — PASS, 10 tests. These are separate from the scheduler/runtime checks.
- `docker compose --env-file .env --file infra/compose.yaml --profile m04 build airflow` — PASS. Image was pulled/built locally; the first pull/extraction took several minutes. `airflow version` returned `3.3.2`; `/opt/airflow/project-venv/bin/python -m pip check` returned `No broken requirements found.`
- `docker compose --env-file .env --file infra/compose.yaml --profile m04 up --detach --wait --wait-timeout 300 airflow` — PASS after fixing startup URL formatting. PostgreSQL remained healthy; Airflow initialized its own metadata tables in `airflow_meta`. `airflow dags list-import-errors --output json` returned `[]`.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m04_s01.ps1` — completed its CLI/scheduler/retry/restart/failure phases and exited 0. CLI execution: `m04_cli_376f8571ad694a17a1177624b8039133`, batch `eb57cd2a-b118-544c-bf3f-4d7e36ab5ad4` PUBLISHED. It acquired through read-only source SQL and passed all 11 dbt models/17 tests plus the hook (`PASS=29 ERROR=0`).
- Real scheduler run `m04_retry_e1676243e58243dab3a449b0aa296d9a` — SUCCESS. One intentional post-raw failure retained its failed acquisition/raw and left the prior checkpoint pointer unchanged. Collection then succeeded. A post-freeze failure left a committed manifest; the runner restarted the Airflow service while freeze waited for retry, waited healthy, and verified the identical manifest and same DAG run resumed to publication. Durable stage attempt counts: collect 2, freeze 2, build_and_test 1, publish 1. Airflow's freeze try number was 3 because one restart interrupted scheduling before another platform attempt was allocated; the two counters serve different purposes.
- Published DAG batch `22366796-9f6d-5398-b67e-e249ebc83138` — PUBLISHED. A SHA-256 signature over stable business history/current/marts excluding release IDs matched the direct CLI baseline. Final stable figures: 3 order versions, 3 archived line rows, 18 evidence links, 1 current order/line, V001 quantity 2 / USD40; PAID / NOT_STARTED / CANCELED. Raw/evidence acquisition counts may grow without increasing logical versions.
- Real scheduler run `m04_failed_27a0d63208c9474491a6da1907f5955a` — FAILED by deliberate dbt test injection. Batch `32fff8da-4eac-54c2-af47-12f5b9d3093e` — FAILED. The build had exactly five durable attempts (1-4 RETRYABLE, 5 FAILED), and required publication was never run. The stable business signature and publication pointer remained on the successful DAG batch.
- Clear-phase review exposed an insufficient assertion in the initial runner: Airflow had not selected any task, so try_number was still 5. Inspection of Airflow 3.3.2's installed `task_clear`/`SerializedDAG.partial_subset` showed the option called `--task-regex` performs substring matching here. The probe now uses `build_and_test --downstream`, a one-second interval verified to contain only the target logical date, asserts actual selection, and waits for task try_number >=6 before accepting the final failed state.
- Corrected clear phase was rerun separately on the same deliberately failed run: `Get-Content tests/m04_probe.py -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T airflow /opt/airflow/project-venv/bin/python - clear --execution-id m04_failed_27a0d63208c9474491a6da1907f5955a` — PASS. `cleared_status` returned failed only after the new execution. The `budget` probe returned PASS; final metadata confirmed build_and_test failed at Airflow try 6 and the failure watcher at try 2, while platform build attempts remained exactly 5. Publication stayed `22366796-9f6d-5398-b67e-e249ebc83138`. The final failed artifact was checked to contain only the injected dbt test failure, not unrelated model errors.
- Runtime boundary assertions — PASS: no `/fixtures`, no `/var/run/docker.sock`, no WEBSITE_WRITER_PASSWORD or MARKETPLACE_WRITER_PASSWORD in the Airflow service environment. Production-code search found no source-state/golden/truth-ledger reads.
- `Get-Content tests/m01_acceptance.sql -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T postgres psql --set ON_ERROR_STOP=1 --username postgres --dbname data_platform` — PASS, `M01 database contract PASS`, after Airflow/recovery checks.
- Final `git diff --check`, whitespace inspection of new task-owned files, Python compile/PowerShell parse checks, and `git diff --cached --quiet` — PASS. Runtime credentials/logs/dbt outputs remain ignored; all M04 source/docs changes are unstaged.
- Initial startup failure: metadata URL helper used `print`, causing Airflow to request database `airflow_meta\n`; switched to `sys.stdout.write`. Failed startup did not reset/delete project databases. An initially tightened clear-phase assertion correctly failed when the old regex selected no tasks; the corrected selector then passed.

## M04 checks not run / limits

- No source/volume reset, remote push, marketplace implementation, dashboard, or M05 work was performed. M04 changes are left unstaged for review; the only requested commit was M03.
- The corrected clear phase and its stronger assertions were rerun directly against the same exhausted run, rather than rerunning the entire multi-minute acceptance script. All modified clear/budget checks passed; the unchanged earlier CLI/retry/restart/failure phases had already run successfully through the real scheduler.
- Restart evidence covers committed raw/manifest state and scheduler retry resumption. A hard kill during a database transaction/dbt process, host loss, DAG timeout before the failure watcher, or extended database outage was not fault-tested. If the watcher cannot execute, stop concurrent work, inspect the active run, and explicitly invoke the controller's abort stage before a new replay cycle. These broader campaigns remain M08 scope.
- The source simulator was already at final S01 state 0914 and earlier observations came from retained M02 raw. This is not a clean-volume all-source end-to-end demo or an automatic production schedule. No performance benchmark is claimed.

## M03 decisions and review points

- The M01 target dictionary was reviewed before models; no new target columns or dependent DDL were needed. Candidates use the stable table column order and FK-safe publication order. Business SQL lives exclusively in dbt; Python owns manifest/run metadata, test-artifact verification, and publication copies.
- Runtime: dbt Core 1.11.16 with dbt-postgres 1.11.0, Python 3.12.12 image pinned by digest; all resolved Python dependencies are pinned in `requirements/m03.txt`. Two dbt threads are used. This is a tested local compatibility choice, not a performance benchmark.
- `freeze` records eligible committed raw IDs explicitly. Only successful website acquisitions enter the manifest; failed acquisition evidence stays in raw. Successful replays retain their evidence rows but do not add source versions. A lifecycle guard rejects another active FROZEN/BUILDING/TESTED batch before candidate rebuilds; an interrupted batch requires explicit inspection/abort.
- Website content fingerprints use SHA-256 over the six order/child arrays, excluding catalog/customer/acquisition/mapping metadata. Object keys are sorted and array order is preserved, matching the approved website fixture utility. Snapshot IDs include source/account/order/update/fingerprint, independently of mapping/transformation/batch versions. Latest current state uses source update time; equal-time content conflicts fail a required test before publication.
- Scoped exact variant mapping and unique SKU fallback preserve source line facts. Ambiguous/conflicting identifiers are not guessed. `s01-v1` is treated as immutable during the run; broader missing-mapping remediation is not claimed by this milestone.
- dbt builds candidates only in `build` as `platform_transform`. A batch becomes TESTED only when its matching `run_results.json` and `manifest.json` invocation contains successful results for every project model/test. Hooks are excluded from that required node set. Artifacts remain under ignored `runtime/dbt/<batch UUID>/`.
- `platform_publisher` requires TESTED status and matching candidate batch identity. It copies website rows and updates release metadata in one transaction; failed attempts retain run audit separately. Published tables are read by `platform_report` in a read-only REPEATABLE READ transaction. Normal transform/publish images contain no fixtures; only the parity test mounts fixture files read-only.
- `mart.source_health.coverage_state` stays UNKNOWN: a recent successful checkpoint alone is not proof of uninterrupted coverage. The model retains available checkpoint, acquisition, backlog, exception-count, and publication fields.

## Exact M03 checks and outcomes

- Starting branch/commit/file inspection: `main` at `6c74517`, only M02 changes plus pre-existing `HANDOFF_SHA256SUMS.txt`. Git identity was configured. `git diff --check` and staged diff inspection passed before the requested M02 local commit. Initial Git index write was sandbox-denied; the authorized retry succeeded. Post-commit state contained only the pre-existing untracked file before M03 edits.
- `python -m py_compile transformation/batch.py transformation/publish.py tests/test_m03_fingerprint.py` — PASS. PowerShell parser over `infra/scripts/run_m03_s01.ps1` — PASS. Compose configuration validation — PASS. Boundary search found no fixture/expected/source-state/truth-ledger reads in production M03 code.
- From `fixtures/s01/`, `python verify.py` — PASS, 10 offline checks; `python -m unittest -v test_tools.py` — PASS, 10 tests. These remain offline checks, separate from the runtime results below.
- `powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m03_s01.ps1` — PASS, exit 0 on the final pinned build. Published batch: `8db63541-de4c-4f0b-9af9-71679123201f`; failed acceptance batch: `1ba8328e-9fc4-4088-8a27-a9eada995a3c`.
- The final successful dbt invocation built 11 models and passed all 17 data tests plus its hook: `PASS=29 WARN=0 ERROR=0 SKIP=0`. Both batches froze 16 eligible raw IDs. Publication produced 3 distinct order versions, 3 archived line rows, 16 snapshot evidence links, 1 current order, and 1 current line. Retained acquisition replays did not inflate source-version counts.
- Runner fingerprint test (`tests/test_m03_fingerprint.py` in a test-only container with read-only fixture mount) — PASS: SQL canonical bytes/SHA-256 equal Python fixture behavior on 8 cases (including the three scheduled website business objects, missing/null, ordered arrays, nested objects, and Unicode), and all 16 retained observations.
- Failure acceptance — PASS: exactly `test.multi_channel_orders.injected_failure` failed; every other node passed (`PASS=28 ERROR=1 SKIP=0`, including hook). Batch transitioned to FAILED. An actual publisher attempt rejected it with `only a TESTED batch can be published`. The following `tests/m03_acceptance.sql` returned `M03 website dbt/release PASS` and confirmed the successful publication stayed active.
- `tests/m03_report.sql` was piped through Compose to authenticated TCP psql as `platform_report` — PASS. Stable report results: W1001 PAID / NOT_STARTED / CANCELED; WI1001 maps to V001, quantity 2, USD40 merchandise; order activity 1 / USD40; product activity V001 / 2 / USD40. Publication stayed on batch `8db63541-de4c-4f0b-9af9-71679123201f` after the failed build/publish attempt.
- Final direct DB query confirmed 3 history rows, 3 line-history rows, 16 evidence links, 1 current order/line, and separate FAILED TRANSFORM/PUBLISH run audits for the rejected batch. `git diff --check`, trailing-whitespace inspection of new task files, and `git diff --cached --quiet` — PASS; M03 changes remain unstaged and no credentials/runtime artifacts are included.
- `Get-Content tests/m01_acceptance.sql -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T postgres psql --set ON_ERROR_STOP=1 --username postgres --dbname data_platform` — PASS, `M01 database contract PASS`, after M03 materialization.
- Intermediate failures retained in audit: the first build used unsupported `MIN(uuid)` in three marts; replaced with the frozen batch UUID. A later all-passing build was conservatively rejected by artifact validation because a hook was counted alongside model/test nodes; corrected the node set and explicitly marked that stopped batch FAILED. No failed candidate was published. Earlier accepted run was batch `c01e0fde-ece5-4097-8484-6249364739e9`; final acceptance also exercised repeatable publication from the same raw manifest.

## M03 checks not run / limits

- No volume reset, source playback, or acquisition rerun was required for M03: it used the existing retained M02 raw data. PostgreSQL volume, raw audits and source data were preserved.
- Runtime checks cover approved website S01, not marketplace fingerprints, general JSON numeric encodings, arbitrary commerce states, invalid-source quarantine/remediation, concurrent manual dbt commands, or multi-writer stress. The shared build schema relies on the documented serial lifecycle; mapping versions must not be edited in place during a run.
- No full exception-queue remediation or missing-mapping fault campaign was run; the S01 mapping is complete and candidate mapping failures remain explicit. Broader recovery campaigns belong to M08.
- No Airflow runtime, DAG, dashboard, or performance benchmark was run. Stop before M04; it will orchestrate these reusable acquisition/batch/dbt/publication commands.

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

Owner review of the unstaged M04 changes. Suggested owner commit: `feat: orchestrate website pipeline with Airflow`. After review, select M05 explicitly; do not start it automatically.

## Session update template

- Selected milestone / scope:
- Starting branch / commit:
- Files and behavior changed:
- Technical decisions and draft/approved status:
- Exact checks / results / not-run checks:
- Remaining issues and next task:
- Suggested owner commit message and files to review; Codex leaves changes unstaged unless explicitly asked otherwise.
