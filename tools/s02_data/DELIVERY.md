# Inspect prepared SIM webhook deliveries

Scope: live source simulation only. No M08D load/fault controller, negative business
data, task-clear or process-kill campaign is implemented here. No new ports or
passwords: use the existing local Compose stack and DBeaver connection.

## 1. Update the SIM on an existing live stack

From repository root with Docker Desktop running. These commands apply additive
SIM migrations and recreate only live-source with its updated image. They do not
reset data or change Airflow pause states. Recreating the worker briefly pauses
emission; it resumes retained progress. Do not run during another acceptance run.

```powershell
$compose = @('--env-file','.env','--file','infra/compose.yaml')
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Compose unavailable' }

# PostgreSQL must already be running. No reset/bootstrap of existing volumes.
foreach ($migration in @('001_s02_temporal.sql','002_local_playback.sql','003_live_batches.sql','004_delivery_schedule.sql')) {
    docker compose @compose exec -T postgres psql -X --set ON_ERROR_STOP=1 `
        -U postgres -d marketplace_sim -f "/migrations/marketplace_sim/$migration"
    if ($LASTEXITCODE -ne 0) { throw "SIM migration failed: $migration" }
}

$live = $compose + @('--file','infra/compose.live.yaml','--profile','live')
docker compose @live build live-source
if ($LASTEXITCODE -ne 0) { throw 'Worker build failed' }
docker compose @live up --detach --no-deps --wait --wait-timeout 180 live-source
if ($LASTEXITCODE -ne 0) { throw 'Worker startup failed' }
```

Precondition: source APIs and receiver already run with the live overlay. If this
is not an initialized live stack, follow the existing [live setup](README.md),
including `.env` reader passwords and M01-M07 prerequisites, then run `live-up`
once. Do not pass a retained isolated-test config or swap datasets in Airflow.

## 2. Choose inspection-only or live generation

To store and inspect source plans **without admitting to live APIs/sender**:

```powershell
python -m tools.s02_data prepare --config tools/s02_data/config/sim_delivery_demo.json
if ($LASTEXITCODE -ne 0) { throw 'Prepare failed' }
```

Prepare uses a fixed dataset name and refuses overwriting it. Inspect the printed
dataset/campaign identity; change dataset name in your own config for another
prepared dataset. It is normal that prepared-only rows have no live admission,
no actual sends and no core data. Do not use legacy playback for this plan version.

For actual sending on the current live stack:

```powershell
python -m tools.s02_data generate --config tools/s02_data/config/sim_delivery_demo.json
if ($LASTEXITCODE -ne 0) { throw 'Generation failed' }
docker compose @live logs --tail 60 live-source
```

Each generate adds a new unique dataset suffix; never overwrites old data. It
checks updated-worker capability before preparing new planned data. Config paths
are arbitrary; copy/edit this profile in the same directory if desired. No API
GET, DAG or Docker startup generates orders automatically.

## 3. DBeaver: marketplace_sim

Get the existing host binding without printing credentials:

```powershell
docker compose @compose port postgres 5432
```

Use that host port with your existing `.env` credentials, database marketplace_sim.
Run [inspect_delivery.sql](inspect_delivery.sql):

1. Overview prints the resolved manifest and admission clock. For prepare-only,
   inspect that campaign with a LEFT JOIN to deliveries/schedule; effective live
   times do not exist until admission.
2. Timeline query selects the latest admitted `sim-delivery-demo` batch. It shows
   source version, message, omission, planned/effective due time and actual progress.
3. Counts are scoped to that batch, not all retained data. Adapt the name prefix
   for a differently named profile. No dataset selection is needed in pipeline.

Expected for the provided profile: four Etsy orders, eight logical notifications,
two omitted notifications, ten planned sends; two non-omitted shipped orders
selected for reorder. The duplicate order has three planned sends for each of
its two messages, with the same message ID. No duplicate orders are inserted.
The manifest stores selected reordered order IDs, checksum and last_due_at.

Re-run SELECT after effective last_due_at. With a healthy receiver, ten child rows
eventually have completed_at, last_http_status2xx, last_error_code NULL. Actual
send_count sum is at least ten; network failures/lost ACKs can increase it. Parent
delivered_at is first successful ACK, not proof that all child sends completed.
Omitted messages have no child rows and no sends. Check actual receiver audits
separately; source-side HTTP ACK is not full warehouse acceptance.

Source duration is two minutes, plus any delivery tail/retry/tick delay; this is
not a two-minute pipeline SLA. Receipt GET always serves current visible source,
not the version mentioned by an old notification. No history is fabricated.

## 4. Optional automated SIM regression

```powershell
python tests/test_s02_delivery.py
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/check_sim_delivery.ps1
```

The second command creates temporary PostgreSQL/CLI containers on a private
internal network, no host ports/owner env or scheduler. It validates full loading,
real SIM API/signed HTTP sends, retries/ACK ambiguity and schema guards. It removes
only its unique disposable containers/network afterward; it is not the environment
to inspect in DBeaver. Allow roughly448MiB container memory plus Docker overhead;
do not run if your Docker VM has insufficient headroom. It never stops owner services.

Runtime scope explicitly excludes real warehouse receiver integration, dbt/publish,
Airflow scheduling, load/soak and broader M08C recovery acceptance.

## 5. Storage contract

Migration [004_delivery_schedule.sql](../../migrations/marketplace_sim/004_delivery_schedule.sql)
extends only the synthetic source database. Existing source/version rows and
warehouse source interfaces do not change.

`s02.deliveries` remains one logical notification. Added provenance fields are
`source TEXT NOT NULL DEFAULT 'etsy_sim'` (only etsy_sim),
`account_id TEXT NOT NULL DEFAULT '7001'` (only7001) and
`source_sequence INTEGER NULL` (>0). A composite FK links campaign/source/account/
receipt/sequence to `s02.versions`. Legacy notifications can retain NULL sequence;
version1 plans require a version reference before sealing.

`s02.delivery_schedule` is one planned physical send, keyed by
`(campaign_id TEXT, message_id TEXT, attempt_no INTEGER)` (all NOT NULL, attempt>0),
with a parent FK to deliveries. `due_at TIMESTAMPTZ NOT NULL` is planned source
time, shifted by the live admission clock, not a source-version timestamp.
`send_count INTEGER NOT NULL DEFAULT0` is nonnegative actual attempts. Nullable
TIMESTAMPTZ fields are last_attempt_at/next_retry_at/completed_at; nullable status
fields are last_http_status INTEGER (100..599) and last_error_code TEXT
(TIMEOUT/CONNECT/HTTP/TRANSPORT). A completed send requires a successful2xx,
positive count and no pending retry/error. Counters cannot decrease.

Seal guards require complete plans, contiguous attempt numbers, nondecreasing
due times per message and no send preceding source visibility. Omitted messages
have no child sends. Sealed identity/timing is immutable; only progress may
advance, and completed rows cannot change. Marketplace reader roles cannot read
this test ledger. Duplicate sends share one logical ID; they never duplicate an
order or its source version.
