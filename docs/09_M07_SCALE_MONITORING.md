# M07 revision: bounded multi-channel reporting and measured processing

Owner approved 2026-10-29. This supersedes the unbounded reader/combobox and
table-only monitoring in 08_M07_REPORTING.md, not S01 or its review rules.
English UI: Multi-channel Overview, Order Operations, Pipeline Monitoring.
No stage/commit/push, user-data reset, source-contract change or M08 generator.
The implementation-time Git restriction above is superseded only for the owner's
explicit 2026-10-30 request to create the local M07 milestone commit. No push.

## Finalized contracts before dependent migration 008

- Report queries filter/aggregate in PostgreSQL. One read-only REPEATABLE READ
  transaction per rendered panel includes publications, summary and bounded page/
  selected detail. Options are a separate small lookup, not displayed business
  figures. No all-order/line/history fetch or all-ID dropdown. Currency is isolated.
- Business date range inclusive UTC, maximum 366 days. Default historical fixture
  dates come from a small min/max lookup, explicitly labeled, not today's workload.
  Monitoring uses real processing UTC, separate last-1h/6h/24h/7d control.
- Order Explorer supports exact order-ID search, channel/account, reason/group,
  deterministic keyset seek on (source_created_at,source_system,account,order_id),
  50 rows default/max 100. Fetch page_size+1 only. Cursor embeds filter signature
  and source publication mapping; mapping/filter change resets to first page with
  notice. No browser-lifetime transaction or deep OFFSET. Detail fetched only by
  selected composite key, max 100 items/history/allocations per collection with
  explicit truncation notice. No implication of complete history if capped.
- Summary/charts count ALL filtered matches, not page rows. Channel volume means
  unique published orders, units and observed versions; raw pages/attempts/replays
  are never labeled new orders. Product filter affects only activity line metrics.
- SQL report review projection matches the approved Python rule oracle exactly;
  parity tests cover canceled/requested/unknown/multiple reasons. It is presentation
  classification of existing dbt-normalized states, not new canonical states.

| New object / grain | Fields and invariants |
| --- | --- |
| `report.operations_orders` view, one current order | existing safe order columns + `review_reasons TEXT[]!`, `data_issue BOOLEAN!`; mapping issue uses EXISTS not a multiplying join |
| `ops.execution_measurements`, one actual stage/slot attempt | measurement_id UUID PK, run_id UUID FK, attempt_id UUID nullable FK, source_system/account TEXT!, validation_mode TEXT! s01/runtime, stage TEXT! (collect/freeze/build_and_test/publish/source_slot/release_slot), started_at TIMESTAMPTZ! actual UTC, finished_at TIMESTAMPTZ nullable, duration_ms DOUBLE PRECISION nullable >=0 (monotonic), outcome TEXT! RUNNING/SUCCEEDED/FAILED/TIMED_OUT/INTERRUPTED; null duration for interrupted process, never backfill old timings; immutable identity |
| `ops.scheduler_observations`, latest sample per DAG | dag_id TEXT PK, source_system/account TEXT!, is_paused BOOLEAN!, latest_run_state TEXT nullable, scheduler_heartbeat_at TIMESTAMPTZ nullable, observed_at TIMESTAMPTZ! real UTC; collector writes only sanitized fields |
| `ops.processing_work.recorded_at` | nullable TIMESTAMPTZ; insert trigger sets actual DB clock for new rows only; old rows remain null, never invent enqueue ages |
| `report.execution_measurements`, `report.scheduler_observations`, `report.work_backlog` | explicit safe projections of above; report role SELECT only, no error text/log refs/raw/credentials; backlog counts by state, oldest pending recorded_at null if any pending enqueue clock is unknown |

Indexes: deterministic order seek, exact order-ID lookup, per-order history,
source/time operational measurements and runs/work. Validate real plans using an
uncommitted synthetic 100k-row target-data benchmark; rollback all test rows.
This is a report query benchmark, NOT source ingestion or million-order capacity.

## Architecture corrections, scope and limitations

- Move durable collect before the global release barrier. A source/account session
  lock protects its cycle; independent sources may collect concurrently. Keep the
  existing global freeze/build/test/publish coordinator and frozen-manifest safety,
  including retry/resume of active batches. Do not reset five-attempt budgets.
- Measure slot waiting separately from stage execution with actual UTC timestamps
  and monotonic duration. Preserve historical S01 observation clocks untouched.
  New stage telemetry only; old run times are not reinterpreted as execution time.
- A minimal observer outside DAGs samples Airflow metadata with airflow_app and
  writes sanitized samples using platform_ingest. Report service never receives
  either credential. Sample age >90s or missing heartbeat >120s is unknown/stale,
  not healthy. Paused is distinct from no traffic; no health claim from no failures.
- Monitoring shows attempts per time bucket/channel, terminal error counts/rate
  (FAILED/TIMED_OUT/INTERRUPTED over terminal measured attempts), p50/p95 with sample
  count, stage and slot duration, recorded running state, backlog and freshness.
  Lists filter channel/time BEFORE LIMIT. Historical/replay traffic is labeled
  separately by frozen validation mode; no fabricated source throughput.
- Backlog excludes SUCCEEDED work; PENDING/LEASED/FAILED/DEAD_LETTER remain
  distinct states. Age is actual oldest recording time, unknown if any included
  work lacks that clock. Terminal successful inventory is not outstanding work.
- Current dbt candidate builds still replay retained source history and publication
  replaces a tested source snapshot atomically. This is a known remaining large-
  volume write/compute limit, not a million-order throughput guarantee. Incremental
  model/release redesign needs its own correctness/performance acceptance; do not
  silently change per-row publication lineage or weaken failed-release protection.
- Website acquisition still materializes a consistent window payload, while the
  local Airflow standalone and PostgreSQL share one host. These are additional
  ingestion/resource ceilings. SQL pagination fixes report memory/transfer, not
  every upstream scaling problem. Streaming/chunked extraction needs separate
  source snapshot/checkpoint correctness tests; no unreviewed S01 interface change.
- Normal UI refresh is manual; no result cache. Business and monitoring clocks and
  observation samples are labeled independently; no globally synchronized release.

## Acceptance

1. Preserve S01 totals/review queue and source/account/currency/money/state rules.
2. Bound pages/details/lookups; exact search and all-match aggregates; same IDs in
   different accounts; cursor invalidation on filters/publication change.
3. Real DB report-role RR/read-only/secret tests; UI page navigation, search, next/
   previous page, selected order, empty/unavailable states and actual chart data.
4. Rollback 100k synthetic target rows, EXPLAIN ANALYZE page/lookup, returned rows
   <=page size, report measured timings; no claim of production ingestion capacity.
5. New controller source/release lock-order tests and real stage/timeout telemetry;
   measured collection before barrier, retries reuse manifests/budgets, failed
   tests cannot publish. At least one real current-code CLI pipeline and observer
   sample, not just generated metrics. Preserve M05/M06 acceptance and fixture tests.
6. Update STATUS exact commands/failures/not-run checks; leave M07 unstaged, stop M08.

## External design references (checked 2026-10-29)

- [PostgreSQL 16 LIMIT/OFFSET](https://www.postgresql.org/docs/16/queries-limit.html)
  explains skipped OFFSET rows still require computation. Decision: indexed keyset
  pages rather than deep offsets; local EXPLAIN is evidence, not documentation alone.
- [Streamlit dataframes](https://docs.streamlit.io/develop/concepts/design/dataframes)
  distinguishes browser table rendering/lazy loading. Our SQL filtering/pagination
  occurs before constructing the dataframe, not merely browser virtualization.
- [Airflow metrics](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/logging-monitoring/metrics.html)
  documents task/scheduler metrics. Our minimal DB measurement/observer is a scoped
  local implementation, not a replacement for production metrics/alerting storage.
