# M07 multi-channel operations workspace

English, read-only Streamlit on localhost. Current contract:
[scale/monitoring](../docs/09_M07_SCALE_MONITORING.md); preserved review rules:
[reporting](../docs/08_M07_REPORTING.md). No source actions, raw payloads, fixtures,
writer credentials or Docker socket in report. Isolated `scheduler-observer` reads
Airflow metadata and exports only sanitized samples; it has no HTTP endpoint.

## Run / acceptance (PowerShell, repository root)

Keep existing M01–M06 S01 evidence and root `.env`; never reset volumes.
Golden tests require three published sources; this runner does not initialize S01.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run_m07_report.ps1
$LASTEXITCODE
```

Expect exit 0 and final `M07 report PASS`. Migrates 006–008 idempotently, builds
report/observer, waits for report health, samples scheduler and runs SQL/roles,
rules, bounded query/UI/security tests. It does not run pipeline transformations.
Open **http://localhost:8501** (`REPORT_PORT` changes only host port).
For startup after migrations:

```powershell
docker compose --env-file .env --file infra/compose.yaml --profile m07 up --detach --build --wait --wait-timeout 180 report scheduler-observer
```

Airflow must already have its M06 schema/DAG metadata for sampler success. After
changing orchestration code, rebuild/recreate Airflow when no active runs exist:

```powershell
docker compose --env-file .env --file infra/compose.yaml --profile m04 up --detach --build --wait --wait-timeout 300 airflow
```

No DAG is automatically unpaused by M07. A fresh but paused DAG is not a broken
pipeline. Samples older than 90s / scheduler heartbeat older than 120s show Unknown.
Changing `.env` requires recreation, not restart. Do not expose unauthenticated UI
publicly. Exact checks/evidence and not-run limits are in STATUS.

## Owner review walkthrough

1. **Multi-channel Overview**: S01 = 3 published orders, 6 observed versions,
   6 ordered units, USD124 merchandise and USD124 original order totals. Per-channel
   bars compare orders/units/reviews/versions. Source-created daily trend is a
   historical date chart, not processing throughput. Product top20 + exact product
   filter affect line metrics only: V002 = 2 units/USD44, still 3 order totals.
2. **Order Operations**: all-match summary = 3 orders, 1 review (eBay partial),
   1 canceled website, 0 mapping issues. Switch worklist/reason or exact order ID.
   All orders means searchable cohort, NOT loading all orders: max50 per UI page,
   indexed keyset next/previous, no deep OFFSET. Inspect selector contains this
   page only (max50); use exact ID for a known order. Filters/publications reset
   cursor/detail. Payment/fulfillment/cancellation stay independent. No invented
   overdue/SLA/refund/write-back. Canceled takes precedence over review rules.
3. Inspect Etsy: SHIPPED/UNKNOWN is not a fulfillment task. Retained history
   Website/eBay/Etsy = 3/2/1. Only eBay FUL001 has a recorded blue2 allocation;
   Etsy order-level shipping is not a line/parcel bridge. Detail reads selected
   composite key only, collections max100 with explicit truncation notice.
4. **Pipeline Monitoring**: actual UTC last1h/6h/24h/7d, all/runtime/s01 mode;
   stage attempts over time/channel, outcomes, stage/slot p95 with sample count,
   duration time series, backlog and DAG pause/heartbeat. Old executions have no
   duration backfill. No observations is Unknown, not zero healthy traffic.
   Attempts/replay are NOT newly acquired unique orders; new-order throughput is
   unavailable without a first-publication ledger. Recent drilldowns filter before
   limiting to100. Backlog is current, independently of processing time filter.
5. Refresh manually after publication; no cache/push/auto-refresh. Business panel
   summaries/charts/page/selected detail/publication map share one read-only RR
   transaction. Options and monitoring have separately labeled read snapshots.

One currency; inclusive UTC order-created range max366days. Empty cohort = zero,
missing money = Unknown. Last good publication survives a failed new build.
Availability/failures remain visible; published/checked does not imply coverage.

## Architecture and scale checks

Read in order: docs09 → migration008 → reports/data.py → operations.py (rule
oracle) → app.py → telemetry.py / polling.py / scheduler_probe.py → tests.
Business SQL transformations remain dbt-owned. SQL report review classification
is presentation-only and tested against all120 combinations of the Python oracle.

Optional target-query benchmark (100k synthetic target orders/history in one
transaction, automatically rolled back; no source load generator):

```powershell
Get-Content tests/m07_scale.sql -Raw | docker compose --env-file .env --file infra/compose.yaml exec -T postgres psql --username postgres --dbname data_platform
$LASTEXITCODE
```

Do not run during active publication. Check final rollback PASS and EXPLAIN
actual timings. Full retained-history dbt rebuild and source-snapshot publish
remain known large-volume limits. This benchmark does not certify million-order
ingestion. Browser visual acceptance is separate from AppTest/HTTP.
