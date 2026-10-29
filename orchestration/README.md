# M04 bounded website workflow

M06 Etsy receiver, independent inbox/recovery schedules and acceptance commands:
[ETSY.md](ETSY.md). The receiver remains outside all DAGs.

Current capability: this guide describes the implemented manual S01 workflow.
M05B also implements opt-in periodic website/eBay polling. See
[the polling guide](POLLING.md) for startup, environment settings, durable windows,
shared-build serialization and the real scheduler acceptance runner. This manual
DAG retains its approved S01 behavior; schedules do not create new source data.

`dags/website_orders.py` is a thin Airflow 3 DAG:

```
collect -> freeze -> build_and_test -> publish
    \________ terminal failure watcher ________/
```

Each task invokes `python -m orchestration.website_workflow --stage <stage>`.
That command reuses the M02 collector, M03 batch CLI, dbt build/tests, and M03
publisher. No business SQL or simulator playback belongs in the DAG. It can
also run without Airflow using `--stage all` and an explicit execution ID.

## Persistent identities and budgets

The execution ID deterministically identifies the workflow run, transform batch,
and child run identities. A workflow controller is recorded as a RECOVER-stage
`ops.pipeline_runs` row with stream `website_workflow`; actual ACQUIRE, TRANSFORM,
and PUBLISH operations retain their own rows and Airflow context.
`ops.task_attempts` uses the existing unique `(run_id, task_name, attempt_number)`
key. Each stage has a maximum of five durable attempts, allocated while locking
its parent run. A process interrupted during RUNNING consumes its attempt; the
next attempt marks that audit failed rather than resetting the counter.

Airflow allows four retries after the first invocation. Clearing a task cannot
reset the database counter. Successfully completed stages become no-ops under
the same execution ID. A new replay cycle requires an explicit new execution ID.

Freeze retries reuse the same batch/manifest. Build retries reuse its frozen raw
IDs and processing versions. Publication retries recognize an already published
batch, including a crash after publication commit but before task completion.
When retries are exhausted, the failure watcher marks an active batch FAILED,
records workflow failure, and remains a failing leaf so Airflow reports FAILED.
An aborted/failed run retains its raw evidence and the previous stable release.

One active DAG run and one active task per DAG are permitted; the existing M03
batch guard also protects the shared candidate schema. Do not run manual M03
builds concurrently with this workflow. The Airflow container receives service
credentials to invoke those roles but no simulator-writer credential, fixture
mount, Docker socket, or marketplace backing-store access.

## Local service

The image pins Airflow 3.3.2 / Python 3.12 by digest, with LocalExecutor and two
worker slots. Airflow uses only `airflow_meta` for its own metadata. Project/dbt
dependencies are installed into a separate virtualenv so the M03 lock does not
modify the Airflow environment. `standalone` starts local scheduler, API/UI,
and DAG processing components; this is a development deployment.

Prerequisite: M01-M03 have passed, retained website history contains three
versions, and the website simulator currently holds final S01 state 0914.
M04 never resets the source or recreates earlier unobserved source states.

```powershell
docker compose --env-file .env --file infra/compose.yaml --profile m04 build airflow
docker compose --env-file .env --file infra/compose.yaml --profile m04 up --detach --wait --wait-timeout 300 airflow
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags list-import-errors --output json
```

Open `http://localhost:8080` (or `AIRFLOW_PORT` if overridden). The local username
is `admin`; its generated password is stored in ignored
`runtime/airflow/state/passwords.json`. Keep that file local. UI credentials are
separate from the PostgreSQL `AIRFLOW_APP_PASSWORD`.

The DAG has no automatic schedule/catchup. Trigger `website_orders` manually.
The defaults represent the final frozen S01 observation: window 09:09-09:15 UTC,
observed at 09:15 on 2026-10-17. Earlier M02 observations remain retained in raw;
the DAG acquires through read-only SQL and transforms the complete retained set.
For another window, explicitly provide timezone-aware `window_start`,
`window_end`, and `observed_at` params consistent with the source playback clock.
Keep all fault-injection params false during normal runs.

For an equivalent direct CLI run inside the same runtime:

```powershell
docker compose --env-file .env --file infra/compose.yaml exec -T airflow `
  /opt/airflow/project-venv/bin/python -m orchestration.website_workflow --stage all `
  --execution-id <new-explicit-id> --window-start 2026-10-17T09:09:00Z `
  --window-end 2026-10-17T09:15:00Z --observed-at 2026-10-17T09:15:00Z
```

## Acceptance and artifacts

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m04_s01.ps1
```

The runner executes the reusable CLI baseline, then a CLI-triggered DAG run
executed by the real scheduler (not a recurring timetable run)
with one intentional collection failure after raw persistence and one intentional
freeze failure. It checks the checkpoint during collection retry, restarts
Airflow while freeze is waiting for retry, and verifies the original manifest
and run resume successfully. It compares stable business results with the CLI.
A second DAG run permanently fails a dbt test, exhausts five attempts, and must
preserve the good publication. Reinvoking the same stage must not grant attempt 6.
It then clears the failed build and downstream tasks for that exact logical date;
the DAG must fail again without allocating a sixth platform attempt.
Fault-injection failures and the final failed DAG are expected acceptance evidence.

Metadata persists in PostgreSQL. Logs, generated UI credentials, and per-batch
dbt artifacts persist under ignored `runtime/airflow/` and `runtime/dbt/`.
The UI shows Airflow task/run state; platform audit remains in `ops.pipeline_runs`,
`ops.task_attempts`, `ops.transform_batches`, and `ops.batch_inputs`.
Stopping/restarting the service does not delete volumes or raw data.

If a hard host/process failure or DAG timeout prevents the failure watcher from
running, first ensure no old task/dbt process is still active. Inspect the workflow
and its artifacts, then explicitly invoke `--stage abort` with the same execution
ID, DAG ID, and window/observation arguments before starting a new replay cycle.
Do not delete source/raw data or reset the persisted attempt counter to recover.
The tested restart case is a retry after manifest persistence; arbitrary process
kills and database outages remain broader recovery-test scope.
