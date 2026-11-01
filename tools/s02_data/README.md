# Manual S02 source data

## Daily live workflow (M08B revision, 2026-11-01)

Primary local path: one existing stack/ports/passwords, no reset or campaign
selector. Legacy replay below is not required for daily use. Actual verification
of this revision is in docs/STATUS.md; old isolated PASS is not certification.

1. Docker must run and M01-M07 migrations must exist. Set stable
   S02_EBAY_READER_PASSWORD and S02_ETSY_READER_PASSWORD in .env. Optional
   LIVE_POLL_INTERVAL_SECONDS defaults60; LIVE_SLOT_WAIT_SECONDS defaults300
   (coordinator wait, not business retry budget).
2. From repository root, start everything once:

```powershell
python -m tools.s02_data live-up
if ($LASTEXITCODE -ne 0) { throw 'Live startup failed; inspect before generating' }
```

This enables a persistent timetable drain signal (including deployment of the
parse-time helper to older running images), leaves active retries runnable and
pauses each periodic DAG only after its runs finish. It waits up to600s, applies
additive source migrations, provisions reader roles, builds/starts DB-backed SIMs,
receiver, live-source worker, Airflow and reporting, checks health/import errors,
then unpauses ONLY website_polling, ebay_polling, etsy_inbox and etsy_recovery.
Existing raw/facts/checkpoints and manual/replay pause states are retained.
A drain timeout leaves the signal set, idle DAGs paused and active DAGs runnable
for retry/inspection, not forcibly terminated. After successful startup the
signal is removed and the four periodic DAGs resume.

3. After LIVE_SERVICES_READY, generate manually whenever you want:

```powershell
python -m tools.s02_data generate --config tools/s02_data/config/observe_6min.json
if ($LASTEXITCODE -ne 0) { throw 'Generation/admission failed; inspect retained batch' }
python -m tools.s02_data live-status
```

No play/start command or per-cycle DAG trigger. Repeating generate appends a new
batch: dataset in JSON is a name prefix; a fresh suffix is printed/persisted.
Preparation-only prepare remains available and does NOT publish to live sources.
Generator admission does not require Airflow uptime or unpaused DAGs. After the
initial live-up it can continue while consumers are stopped (C scenarios); an
unavailable SIM produces a warning, a reachable fixture/replay SIM is refused.
Consumer/worker readiness is checked separately, not used to fabricate a PASS.
After source/reference/mapping writes, READY data is admitted with a persisted
timestamp shift: earliest channel start becomes admission+2s. Relative lifecycle
intervals remain unchanged. This prevents old fake dates falling behind existing
live checkpoints. Original dates and the shift remain inspectable. Exact literal
historical dates require the legacy replay path, not daily live admission.
Six minutes is the source window, not an end-to-end completion deadline.
observe_6min uses120..150s transitions so scheduled reads can observe changes;
quick_6min uses15..30s and is only a fast final-data demo, not the preferred
profile for the strict observed-transition acceptance gate.

4. DBeaver uses your ordinary .env connection. In marketplace_sim:

```sql
SELECT d.name,b.* FROM s02.live_batches b
JOIN s02.local_datasets d USING(campaign_id) ORDER BY published_at DESC;
SELECT * FROM s02.live_website_progress;

-- Count admitted orders, not versions or old unpublished prepare-only datasets.
SELECT o.source,count(*) AS admitted_orders
FROM s02.orders o JOIN s02.live_batches b USING(campaign_id) GROUP BY o.source
UNION ALL
SELECT 'internal_web',count(DISTINCT v.order_id)
FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id);
```

In data_platform inspect core.orders_current, core.order_lines_current,
core.order_snapshot_history and raw.raw_records. Old records remain: total counts
include earlier data. Match source/account/order IDs from the new batch. Verify
real scheduled runs on all four paths and source-to-core reconciliation; green
empty polls alone do not certify data flow. Dashboard uses actual live dates.
Use `SET TIME ZONE 'Asia/Bangkok';` in a DBeaver session to display local time;
UTC and +07 representations describe the same persisted instants.

5. Source-worker diagnostics:

```powershell
docker compose --env-file .env --file infra/compose.yaml --file infra/compose.live.yaml --profile live logs --tail 80 live-source
```

Do not recreate SIM/Airflow with base-only Compose after live-up: that removes the
live overlay. Reuse live-up or both Compose files. No volume deletion is required.
Stopping the worker stops Website/webhook emission, not due marketplace API data.
Complete restart/pause/fault certification remains M08C, not implied by B.
[Design and M08 fault boundaries](../../docs/16_M08_LIVE_LOCAL.md).

Optional six-minute omitted/duplicate-notification example:
`python -m tools.s02_data generate --config tools/s02_data/config/quick_faults.json`.
To make intermediate states easier to observe, use config/observe_6min.json:
120..150s transitions and fully reserved lifecycle quotas. The15..30s quick
example can legitimately finish transitions between polls on a small laptop.
Read-only final source/API/core check (waits for all admitted timelines to finish):

```powershell
python -m test_support.m08b_live_check --wait-seconds 1200 --verify-reread-seconds 600 --require-observed-changes
if ($LASTEXITCODE -ne 0) { throw 'Live reconciliation/reread check failed; retain evidence' }
```

This does not manually run a collector/build. It waits for two scheduled successes
per path, validates final facts/lines/times/mapping against sources, raw evidence
links and omitted/duplicate delivery effects, then (when requested) waits for an
additional scheduled success per path and checks stable logical facts/history
with increasing raw audits. It does not certify all C/D cases. Run without new
generation during its reread phase. Evidence is under runtime/m08b-live-check-*.
For the strict observed-change gate use observe_6min, not only the fast example.
Intermediate states between actual observations are never reconstructed.

<details>
<summary>Historical regression only: selected-dataset preparation and replay</summary>

## Legacy single-dataset preparation and replay

This is the retained replay workflow, not the daily live path. One local
PostgreSQL/Airflow stack, stable `.env` ports/passwords. JSON config and generator
are colocated here; shared source templates retain compatibility imports for old
tests. No automatic generation on startup, GET, schedule or container restart.

## Prepare and inspect before enabling anything

From repository root, with the existing PostgreSQL healthy and migrations M01–M07
already installed:

```powershell
python -m tools.s02_data prepare --config tools/s02_data/config/demo.json
if ($LASTEXITCODE -ne 0) { throw 'Prepare failed; retained LOADING dataset must be inspected, not overwritten' }
python -m tools.s02_data inspect --dataset local-s02-demo
python -m tools.s02_data status
```

Host needs Python stdlib and Docker Compose, not psycopg/YAML packages. Preparation
applies opt-in marketplace migrations, loads all source versions/Website plans,
inserts100 Website customers/30 products/30 variants and90 mappings additively.
Existing differing references/mappings cause refusal. It NEVER inserts warehouse
answers, resets S01 or starts/recreates services. Source Website orders are applied
only during playback, not inserted with their future final status during prepare.
Counts100/30/30 refer to added S02 reference identities, not necessarily total rows
in a retained S01 database. Filter customer_id/product_id/variant_id by `S02-%`
when inspecting references. Prepared Website order timelines are in marketplace_sim
until explicit playback; existing S01 source orders remain unchanged.

DBeaver connects to the ordinary PostgreSQL host port and credentials in `.env`;
same connection for all datasets. Inspect `marketplace_sim.s02.local_datasets`,
`website_versions`, `orders`, `components`, `versions`, `deliveries`; Website
references are in `website_source.public`; mapping in `data_platform.config`.
`coverage` JSON distinguishes planned cases from observed results. READY means
preparation complete, NOT pipeline acceptance PASS. A failed cross-DB load retains
LOADING and may retain additive mappings/references; no automatic cleanup/retry.

## Configure

All supported parameters, defaults, lifecycle/required quotas and examples:
[configuration reference](CONFIG.md).
Omit global start_at/end_at for now..now+5h by default. Set `duration_minutes: 6`
for a six-minute source window (or5 for five minutes); see `config/quick_6min.json`
with compatible15..30s transition delays. This does not start pipeline services,
change schedules or promise end-to-end completion within six minutes. Explicit sample-file dates remain
unchanged. Dates/seeds are resolved once at prepare and persisted, not resampled
by playback. Channel dates individually inherit global values unless overridden.

- `demo.json`: small unequal channel volumes with separate peak hours.
- `coverage.json`: mandatory pending/request/cancel and partial/full cases.
- `faults.json`: opt-in omitted and duplicate signed Etsy deliveries.
- `load.json`: pre-generated workload only, NOT a measured capacity claim.

`orders` counts orders, not events. Separate order_seed/event_seed; missing seeds
are chosen once and recorded in DB manifest. Per-channel date/timezone, peak
weights, basket bounds, branch weights, delays and quotas are validated. Times are
offset-aware, end exclusive. Peak weight is relative rate per unit time, not a
fixed fraction. Events follow source-supported causal branches and may stop
pending at end. Unsupported API/security/crash/data-quality fault injection is
listed explicitly in manifest, not silently claimed covered. Broad faults remain
M08C; load measurements M08D. Current generator does not add Website shipping,
marketplace refunds/cancellations or delivered states absent source evidence.

## Activate only on an approved empty source/warehouse scope

Set the two stable S02 reader passwords in `.env` using `.env.example` names.
Do NOT use/edit an isolated runtime compose.json. The local overlay preserves all
ordinary host ports. Activation refuses existing Website orders, warehouse raw/
current/checkpoints and active/unpaused polling DAGs. Your current S01 environment
therefore requires a separately approved retention/transition plan; do not delete
its volume to bypass this guard. You can still prepare and inspect additively.

```powershell
python -m tools.s02_data start --dataset local-s02-demo --mode replay --at 2026-10-20T01:00:00+07:00 --confirm-local
```

This explicitly builds/recreates local simulator/Airflow services using
`infra/compose.s02.yaml`; no second stack is created. It keeps DAGs paused, so you
can inspect sources first. The mode is realtime or replay1x, never a machine-clock
change. A second initialization/rewind/dataset replacement is refused.

In a separate terminal, run the source-only driver (no random generation):

```powershell
python -m tools.s02_data play
```

The driver applies due Website source transactions and sends signed Etsy messages;
marketplace GET reads preloaded PostgreSQL as-of versions. Keep driver running
while expecting Website/webhook advancement. A slow/stopped driver can delay
source visibility; overlap is not an unlimited late-arrival guarantee. After source
inspection enable website_polling, ebay_polling, etsy_inbox and etsy_recovery ONCE
in the local Airflow UI. Do not trigger generation from a DAG. The opt-in pipeline
reads logical cycle bounds via authenticated simulator HTTP; operational
observations, leases, signatures and timeout clocks remain actual UTC.

For historical replay, select the generated business-date range in the dashboard
(for example2026-10-20), not only today's default date filter. Operational health
and pipeline observation timestamps still use today's actual clock. An isolated
acceptance run does not populate the owner dashboard; inspect its own test DB.

```powershell
python -m tools.s02_data stop
python -m tools.s02_data status
python -m tools.s02_data resume
```

Stop freezes source logical time; it does not kill in-flight tasks or delete/down
containers. Polling skips new cycles while frozen. Resume preserves replay
position (realtime resumes at actual UTC). Ctrl+C interrupts only the driver,
not the logical clock/services: issue explicit stop if you want to freeze sources.
Full crash/pause-resume recovery certification remains M08C.

## Verification status

See docs/STATUS.md and the retained Vietnamese audit document for actual results.
Offline tests do not certify local activation or real schedules. Do not reuse
older temporal acceptance PASS as proof of this changed logical-clock path.

Developer acceptance on a fresh, disposable scope (NOT the everyday prepare/play
workflow): `python -m test_support.m08b_window --confirm-owner-airflow-window
--local-replay`. This flag is valid only with explicit current-task permission to
stop idle owner Airflow. The wrapper restores the exact owner container in
`finally` and compares its health, DAG pause states, protected data signature and
PostgreSQL system identity. It does not stop owner PostgreSQL or activate S02 on
owner data. Test storage is retained; only test containers/network are removed.

The finite profile manually prepares two orders per channel once, replays at1x,
checks omitted Etsy notification recovery, at least two real scheduled successes
per path, final reconciliation and observed-only history, then explicit CLI
dedupe. Source changes finish after about20 minutes; cold build/startup, draining
and replay take additional time. It is not a speed benchmark, realtime-mode
certification or full fault campaign. Exit0 alone is insufficient: also inspect
the test result and owner-window restoration evidence named in the output.

For the final rolling-date/realtime gate, use the same explicitly authorized
wrapper with `--local-realtime` instead of `--local-replay`. It starts the paused
test scheduler first, manually prepares18 orders with actual omitted-date
defaults (now..now+5h), and uses a deliberately strong first-two-minute peak to
observe causal changes within a finite correctness run. It checks persisted
READY config/counts and actual PostgreSQL source time, all four real scheduled
paths, observed-only history, recovery and dedupe. It does not wait five hours or
certify load/realistic peak distribution. No owner S01 activation/reset is needed.
Exact results, not code or CI definitions, determine acceptance in STATUS.

The finite runner follows the manual source-before-polling order: keep polling
DAGs paused until initial due Website transactions and notifications are
materialized. Starting polling against an empty Website and only later inserting
old planned timestamps can advance an empty watermark beyond the overlap. The
runner now has an explicit source warmup barrier and refuses an excessively
late warmup, rather than rewinding checkpoints or manually filling the warehouse.
This is startup correctness, not certification of arbitrarily slow source drivers.
The maintenance wrapper also saves owner-window-start.json before stopping the
owner container. External process-tree termination can bypass Python finally;
inspect that snapshot and target identity before any manual recovery. Never
treat an interrupted acceptance latch as permission to reset a dataset.

</details>

## Recovery and faults

M08C uses a separate explicit case runner, not extra generator status values.
See [recovery guide](../../docs/17_M08C_RECOVERY.md). Existing prepared data and
daily live commands above do not change; no reset or new daily environment.
