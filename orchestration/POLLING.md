# M05B local polling

`website_orders` retains the manual S01 workflow. New `website_polling` and
`ebay_polling` use current-clock bounded windows; `ebay_polling_replay` is a manual
current-clock recovery/test path using exactly the same controller. All new DAGs
are created paused. Airflow metadata retains their pause state on restarts.

## Configuration and startup

Set these in the repository-root `.env` (examples only):

```dotenv
WEBSITE_POLL_INTERVAL_SECONDS=60
EBAY_POLL_INTERVAL_SECONDS=60
POLL_OVERLAP_SECONDS=120
WEBSITE_POLL_INITIAL_START=2026-10-28T00:00:00Z
EBAY_POLL_INITIAL_START=2026-10-28T00:00:00Z
AIRFLOW_UI_USERNAME=admin
AIRFLOW_UI_PASSWORD=
```

Choose the initial starts explicitly for your source's current-clock scope, not
by copying the example date. Generate a recent UTC value in PowerShell with
`(Get-Date).ToUniversalTime().AddMinutes(-2).ToString('o')` if that is the intended
bootstrap interval. First polling requires a start; later cycles use the stored
`orders_polling` checkpoint minus overlap. Historical S01 uses separate `orders`
checkpoints, which polling never rewinds or updates.

Intervals default to 300 seconds and must be >=10; 60 is a convenient local dev
value. A short interval does not guarantee a completed publication that often:
long tasks wait behind one active run per source and globally serialized release.
Changing `.env` requires recreating the service so DAG parsing/tasks see the new
environment; `docker compose restart` alone does not reload its environment.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1
docker compose --env-file .env --file infra/compose.yaml --profile m04 --profile m05 build airflow
docker compose --env-file .env --file infra/compose.yaml --profile m04 --profile m05 up --detach --wait --wait-timeout 300 airflow ebay-sim
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags list-import-errors --output json
```

Verify import errors are `[]`, then enable the desired schedules once:

```powershell
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags unpause website_polling
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags unpause ebay_polling
```

Use the same commands with `pause` to stop creating scheduled work. Running tasks
may finish; inspect them before maintenance or manual transformations. Services
must remain running. Catchup is disabled; after downtime the checkpoint-derived
window covers the gap rather than claiming every missed scheduled interval ran.
Do not run acceptance fault injection while normal schedules are enabled.
Pausing can leave a DagRun label RUNNING while a terminal watcher awaits scheduler
processing, even after business work has finished. Check task states and the
linked operational run/batch before maintenance; do not mark success manually.

The fixed source fixtures do not advance themselves. These schedules can validly
acquire empty windows while rebuilding the retained business history. New
current-clock source changes belong to the separate M08 demo driver, not the DAG.
No marketplace backing-store access or source-writer credential is added.

## Credentials

Database credentials and the synthetic eBay HTTP token remain environment-driven.
Optional `AIRFLOW_UI_USERNAME`/`AIRFLOW_UI_PASSWORD` provision SimpleAuthManager's
local ignored password file at service startup without logging the values.
An empty UI password preserves the existing generated/chosen password file;
it does not reset a previous password. `.env.example` has placeholders only.
UI and `AIRFLOW_APP_PASSWORD` (metadata DB) are different credentials. Changing
PostgreSQL passwords in `.env` is not a database-role rotation mechanism for an
already initialized volume. No credentials should be staged or committed.

## Recovery and audit

One task owns the complete collect/freeze/build/test/publish cycle; each internal
stage retains the existing durable `ops.task_attempts` audit and five-attempt
budget. The cycle's source, DAG/run, requested bounds, validation mode, versions,
overlap and fault configuration are persisted before work. Retrying/clearing the
same run cannot recompute its start from a later checkpoint or switch validation.
HTTP also has at most five attempts per request; at most five failing collection
stage invocations means up to 25 request attempts for one repeatedly failing URL
in a workflow cycle, not an unbounded retry policy. Every response is audited.

A PostgreSQL session coordinator spans the complete release and reuses its own
connection for manifest freeze. Cooperating CLI freezes take the same coordinator
lock. The existing active-batch guard additionally protects manual M04 releases
whose separate tasks span process lifetimes. Another source waits without
allocating business-stage attempts. DB session loss releases the transient lock;
the active durable batch still prevents another source from overwriting candidates
until its owning workflow resumes or is explicitly aborted.

The controller is reusable without Airflow, inside the same runtime:

```powershell
docker compose --env-file .env --file infra/compose.yaml exec -T airflow `
  /opt/airflow/project-venv/bin/python -m orchestration.polling `
  --source ebay_sim --execution-id my-explicit-cycle `
  --window-end <fixed-UTC-upper-bound> --initial-start <explicit-UTC-bootstrap>
```

For controlled recovery use the original execution ID/DAG ID/window and persisted
fault options. `--abort` closes its active batch/workflow without deleting raw;
first ensure no old task/dbt process is still active. An exhausted cycle requires
an explicitly identified new recovery cycle. A host loss/DAG timeout that prevents
the failure watcher from running is still an operator recovery case, not claimed
as a fully tested automatic hard-kill campaign.

`ops.polling_cycles` binds immutable configuration to the parent operational run;
`ops.pipeline_runs` links actual Airflow run IDs and fixed windows;
`ops.transform_batches.validation_mode` binds the dbt artifact to runtime or S01.
Runtime keeps invariant tests but disables only four fixed S01 golden assertions;
the legacy acceptance commands still run all their S01 checks by default.
Publication is source-specific. Live health/dashboard work remains M07.

## Acceptance

After retained M01-M05A setup, with no other active manual batches:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m05b_polling.ps1
python tests/test_m05b_config.py
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_m05b_runner.ps1
Get-Content tests/test_m05b_invariants.py -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T airflow /opt/airflow/project-venv/bin/python -
```

The runner temporarily uses 30-second schedules in its process environment and
restores the owner's `.env`/default settings afterward. It compares direct CLI
results, observes two scheduler-created successful cycles per source, proves
overlapping DAG runs had noninterleaved releases, pauses periodic work, then tests
post-raw/post-freeze faults, service restart and manifest reuse through the manual
eBay replay DAG. It injects a permanent dbt failure, exhausts five build attempts,
clears the task and confirms no sixth platform attempt or failed publication.
Expected final output is `M05B PASS ...`; deliberate failures are expected evidence.
Schedules are left paused for review, data/volumes retained. Run M04/M05A S01
regressions only with periodic polling paused. No clean-volume or changing-source
demo is implied by this acceptance.
