# M06 local Etsy webhook and recovery operation

This is the approved fixed local subset, not a live Etsy integration. Python
handles HTTP, exact-byte verification and raw/ops; dbt owns business SQL; Airflow
orchestrates reusable commands. No provider account/OAuth or production-server
claim. Baseline requires retained M01-M05 website/eBay evidence, not empty storage.

## Startup and credentials

Use repository-root `.env`, based on the new Etsy placeholders in `.env.example`.
The API token and encoded `whsec_` signing key are synthetic local defaults; never
reuse production credentials or publish this development receiver on the internet.
The selected account is shop 7001. Receiver credentials do not include a source DB
writer, publisher password or API token. Airflow needs the API token, not the signing
secret. Only the sender/receiver share the signing key; avoid printing it.

```powershell
docker compose --env-file .env --file infra/compose.yaml up --detach --wait postgres
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/migrate.ps1
docker compose --env-file .env --file infra/compose.yaml --profile m04 --profile m06 build airflow etsy-sim etsy-receiver dbt-transform platform-publisher
docker compose --env-file .env --file infra/compose.yaml --profile m04 --profile m06 up --detach --wait --wait-timeout 300 airflow etsy-sim etsy-receiver
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags list-import-errors --output json
```

Expect import errors `[]`. Host defaults: API `localhost:8082`, test-only controls
`localhost:8092`, callback `http://localhost:8083/webhooks/etsy`, health
`http://localhost:8083/health`. Inside Docker, the API origin is `http://etsy-sim`,
receiver is `http://etsy-receiver:8000`, and PostgreSQL is `postgres:5432`.
Host port overrides do not change those internal addresses.

The standard-library threaded HTTP receiver runs continuously outside a DAG.
`POST -> verify raw bytes -> commit raw/inbox/delivery/work -> 202` is independent
of receipt fetch/dbt/publication. Supported initial worker events are paid/shipped;
other event types remain auditable IGNORED inbox entries, not business updates.
Duplicate deliveries get audit but no second logical work item. Same message ID
with changed bytes returns 409. Invalid signatures/freshness return 401; invalid
shop/URL/body returns 400; persistence failure returns 503, never success ACK.
Bounded transport rejections are labeled separately when no body was read; their
empty audit body is not claimed to be the original webhook body.

## Scheduled operation

New DAGs are created paused: `etsy_inbox` drains pending work, `etsy_recovery`
independently lists modified receipts, and `etsy_replay` is manual fault/recovery
testing. Intervals default to 300 seconds and must be >=10:

```dotenv
ETSY_INBOX_INTERVAL_SECONDS=60
ETSY_RECOVERY_INTERVAL_SECONDS=60
ETSY_RECOVERY_INITIAL_START=
ETSY_FRESHNESS_SECONDS=300
ETSY_LEASE_SECONDS=60
```

Choose an explicit UTC initial recovery start before first enable; to reconcile
the frozen S01 receipt it must include 2026-10-17 09:05 UTC. A recent current-clock
bootstrap can correctly return empty. Subsequent runtime recovery uses its own
`receipts_polling` checkpoint minus default 120-second overlap. Explicit historical
CLI recovery uses `receipts`. Inbox drain has no invented extraction window.

After changing `.env`, recreate with `up --detach --wait`; restart alone does not
reload environment. Then enable only the desired scheduled DAGs:

```powershell
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags unpause etsy_inbox
docker compose --env-file .env --file infra/compose.yaml exec -T airflow airflow dags unpause etsy_recovery
```

Use `pause` instead of `unpause` to stop future scheduling; inspect running tasks
and active batches before maintenance. Keep the receiver alive while jobs are
paused: stored messages wait safely. One valid signed delivery needs no manual
worker command once `etsy_inbox` is enabled. Polling frozen data does not create
orders or imply complete coverage. M08 owns the separate changing-source demo.

## Retry, lease and publication boundaries

Work is claimed atomically with a unique token and expiry. Each claim performs
one HTTP request and consumes one of five durable attempts. Only the current,
unexpired token may complete work; a stale owner's response stays HTTP audit but
cannot become an eligible receipt snapshot. Expired fifth attempts become FAILED.
`etsy_http` retains each physical request body; `etsy_receipt` is its fenced
admission copy, not another HTTP call. Use `ops.etsy_http_attempts` for request
counts and the raw HTTP ID/collection-run links for provenance.
Scheduler ticks, Airflow clears and process restarts never reset work counters.
Terminal failures remain visible; a later drain selects eligible pending work,
not a hidden automatic replay of previously failed work. Coverage remains UNKNOWN.
Recovery refuses a fresh receipt work cycle when that receipt has unresolved
FAILED work; a successful explicit replay links back through `replay_of_work_id`
without clearing the old counter/audit. Periodic scans cannot reset exhausted work.

The recovery-list request budget is five durable attempts per page/cycle. Successful
pages and identified work are reused after interruption; malformed/incomplete/
changing-count/duplicate pages cannot advance checkpoint. Selected transient errors
use bounded retries; 404 does not delete a receipt. Acquisition completion and
tested publication are distinct. Failed business tests preserve the good release.
Source-wide Retry-After cooldown is derived from durable HTTP audit, including
across workflow cycles. Long delays defer work rather than silently clipping the
provider value. Network failures have null wire response status plus transport
metadata; oversized response prefixes are labeled and never admitted as receipts.

Controlled replay of one failed work item is explicit and retains old audit:

```powershell
docker compose --env-file .env --file infra/compose.yaml exec -T airflow /opt/airflow/project-venv/bin/python -m ingestion.etsy replay --work-id <original-work-UUID> --execution-id <new-explicit-cycle-ID>
```

This acquires raw/work only. A later enabled inbox release or an explicitly
identified `orchestration.polling --source etsy_sim --collection-mode drain`
cycle builds/tests/publishes. Do not clear counters or edit raw/inbox rows manually.
All source release commands share the session coordinator and durable active-batch
guard. The immutable manifest/mapping/transformation/validation mode survives retry;
only `etsy_orders` stable rows/pointer are replaced by an Etsy release. Receiver ACK
does not wait for that coordinator. Direct ad-hoc dbt commands are not coordinated.
Etsy DAG retries restore their captured configuration, including recovery scope,
rather than switching to newly loaded environment values. Explicit CLI calls without
`--reuse-cycle-config` reject a changed context. DAG contention waits 15 seconds
before bounded retry, consuming no business attempt; CLI default remains 600.

## Acceptance

Run serially with normal schedules paused and no other manual batch active:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m06_s01.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m06_scheduled.ps1
Get-Content tests/test_m06_unit.py -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T etsy-receiver python -
Get-Content tests/test_m06_receiver.py -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T etsy-receiver python -
Get-Content tests/test_m06_leases.py -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T airflow /opt/airflow/project-venv/bin/python -
$releaseId='m06-security-release-'+[guid]::NewGuid().ToString('N')
docker compose --env-file .env --file infra/compose.yaml exec -T airflow /opt/airflow/project-venv/bin/python -m orchestration.polling --source etsy_sim --collection-mode drain --execution-id $releaseId
```

The S01 runner sends D1/D2/D3 with fresh execution-clock signatures, restarts the
receiver after inbox commit, drains with explicit simulated observation clocks,
and checks tested/failed publication. A separate message scope tests shipped before
paid and a transient receipt 429 retry without increasing business versions.
It does not edit fixed fixture bytes. Replays
retain audit; exactly three additional baseline delivery attempts are expected,
not a global retained count of three. Negative HTTP tests use separate message IDs
and ignored events; its supported duplicate case queues exactly one real work item,
which the explicit security-release cycle above drains/publishes. Lease tests roll
back all DB writes.

The scheduled runner temporarily uses 30-second Etsy schedules and a new isolated
`receipts_test_<UUID hex>` checkpoint stream per campaign, explicitly covers
the frozen receipt for recovery, sends one supported message and observes two real
scheduled successes per Etsy DAG. Website/eBay schedules exercise shared-release
contention. It then tests explicit fault/restart/manifest reuse and exhausted build
budget after a real task clear. Expect a deliberately FAILED run alongside success;
final `M06 scheduled PASS ...` is the relevant result. It pauses participating DAGs
and restores process environment/owner settings without deleting data or volumes.
Do not interrupt the runner or trigger concurrent manual builds during acceptance.

### Recovering a previously interrupted scheduled test

The runner now drains old runs before creating a campaign and again before replay
tests. `POLLING_DRAIN_MODE=true` temporarily changes the four periodic DAGs to
`schedule=None`; they stay unpaused so existing retries/queued runs can complete.
It waits for the latest serialized timetables to confirm the change, then checks
both Airflow run state and platform state before pausing. A timed-out DAG can skip
its failure watcher: `orchestration/draining.py` closes a still-running platform
parent only after Airflow confirms FAILED and no task is executing/queued, through
the existing guarded abort command with captured configuration. It does not retry
an already timed-out DAG or turn that failure into success. It does not clear tasks,
reset attempts, fake success, rewind checkpoints or delete runs. Normal mode is
`POLLING_DRAIN_MODE=false`; manual DAGs always retain `schedule=None`.

For just the recovery step, without a new scheduled campaign:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m06_scheduled.ps1 -DrainOnly
```

Expect `M06 drain PASS`, a zero process exit code and healthy Airflow after config
restoration. A full run also performs this step automatically; run the full script
after drain-only when ready to verify restart/retry/budget acceptance. No need to
repeat S01 solely for this runner fix if S01 already passed.

If draining fails/times out, the script reports the error and retains the running
container's drain configuration instead of pausing stranded retries or restoring
periodic scheduling unsafely. Inspect task logs; recover with `-DrainOnly`. Do not
interpret `No unpaused DAGs were found` or container Healthy as campaign acceptance.
The original error is printed before cleanup, which can take several minutes.
The final PASS marker is emitted only after successful cleanup/config restoration.
Regression checks: `python tests/test_m06_scheduling.py` and
`powershell -NoProfile -ExecutionPolicy Bypass -File tests/test_m06_runner.ps1`.

Combined golden result: 3 orders, 4 lines, 6 units, USD124 and 6 observed order
versions. Etsy contributes one paid/shipped order, one line/unit/USD22 and one
observed version; no paid-only snapshot, delivery/refund claim or parcel allocation
is invented. Exact runs, measured outcomes and unrun checks belong in STATUS.
