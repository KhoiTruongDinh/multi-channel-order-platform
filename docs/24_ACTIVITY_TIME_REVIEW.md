# M08D activity time and staging review

2026-11-14 owner correction: each report uses the clock appropriate to its metric,
not one globally selected date. Implemented bounded daily-cohort model/publisher
scope and clearer UI labels; no universal receipt-date switch or parallel runner.
Actual validation results belong in STATUS. Preserve approved S01 source behavior.

## Findings before the bounded correction

- `*_activity_daily.sql` builds candidate marts. Publication is separate in
  `transformation/delta_publish.py` (live) and `transformation/publish.py` (full).
- Daily models bucket by source-created UTC date. This matches the retained
  creation-cohort definition but is NOT received-data or update throughput.
- `effective_current` combines unaffected retained current with affected
  candidates. Previously daily aggregates processed the effective entire source/account.
- Previously `_merge_mart` deleted source/account buckets absent from candidates. Adding
  WHERE today alone would delete unrelated older days. Recompute scope and
  publisher delete/upsert scope must change TOGETHER.
- Operations UI reads filtered core/report views, not these model files directly.
  Its date/cohort labels and metric queries also need review for receipt semantics.

## Clocks and per-report definitions

| Clock | Meaning / limitation |
| --- | --- |
| source_created_at | Source creation of order, not received day. |
| source_updated_at | Source version change time; can precede arrival by days. |
| raw acquired_at | Current observation clock: Website/eBay use invocation observed_at, including logical replay time. Not universally exact physical receipt. |
| first_observed_at | Earliest observation of one logical source version, not necessarily first appearance of the order across versions. |
| Physical read/response completion | eBay metadata.fetched_at exists; no uniform exact receipt field across all three adapters. |
| published_at / stage telemetry | Warehouse visibility/processing time, not source or receipt date. |

Do not rewrite immutable history, substitute simulator visible time or fabricate
exact arrival timestamps for old rows. A common real-receipt field needs additive
dictionary/DDL and explicit old-data/unknown coverage. Keep live and replay clocks
distinguishable.

Separate metric definitions (not mutually exclusive choices for all reports):

1. Observed activity: each distinct version first observed that day; updates on a
   later day count activity then. Known-version replay/raw retries do not inflate
   logical version counts. Distinct orders active that day is a separate counter.
2. New integrated orders: first appearance of the scoped order that day; subsequent
   changes do not create new-order counts.

Future observed/new-integrated counters need explicit names. Neither is source-created
sales/revenue; summing order money across observed versions repeats the same value.
Example: created10Nov, first received14Nov, updated/received15Nov:
creation cohort10Nov; new integrated order14Nov; observed activity14Nov and15Nov.
A replay of the same known version16Nov is delivery audit, not another version.

## Implemented bounded correction

1. Freeze new eligible raw and affected scoped orders, preserving actual audit.
2. dbt derives old AND new bucket keys. Date/product/currency/mapping changes can
   empty former buckets: persist scope even when no new aggregate row exists.
3. Recompute only dirty buckets at the chosen metric grain. Bootstrap/backfill
   may explicitly cover all days; normal polling must not recalculate all history.
4. Atomically reconcile/delete only keys in that scope, then upsert. Untouched
   dates/channels remain; empty old buckets are explicitly handled.
5. Late data updates its justified date, not blindly CURRENT_DATE.

Finalized helper dictionary precedes implementation in05_TARGET_SCHEMA.md:
source-private candidate_activity_scope(date/source/account/batch) and
candidate_daily_orders(scoped order/source-created timestamp/currency/amount).
Scope is by touched day, recomputing all product/currency buckets WITHIN that day,
not all historical days. Bootstrap includes existing mart dates so stale empty
dates can be removed. Migration013 grants only required mart SELECT access.
No new ingestion-day mart or physical-receipt column is invented in this slice.

Acceptance: midnight, late delivery, replay next day, same-day and cross-day
updates, mapping/product/currency moves, emptied former bucket, untouched history,
restart/retry and full-vs-delta parity. Preserve S01 fixtures/source contracts.

## Staging and duplicate-work review

Saved900 timings, before SQL-style cleanup (CTAS + ANALYZE/client-server elapsed,
NOT JSON-only CPU):

| Staging | Mean seconds | p95 seconds |
| --- | ---: | ---: |
| Website | 0.655 | 1.310 |
| eBay | 0.752 | 0.934 |
| Etsy | 0.156 | 0.311 |

See [23_M08D_BUILD_TIMING.md](23_M08D_BUILD_TIMING.md). Website product aggregate
max5.061s and Etsy unitemized build remainder must not be blamed on JSON parsing
without evidence. No new900/profile executed in this review.

Website flow: frozen raw -> expand order/child arrays -> group by raw+order ->
join/shape business JSON -> fingerprint -> intermediate version dedup -> type/
mapping/status models -> tests -> publication. Staging is ALREADY a materialized
table. MATERIALIZED CTEs prevent important repeated expansion inside that query;
large window arrays still merit profiling.

Logical dedup occurs AFTER shaping/fingerprinting, so duplicate raw can still
repeat computation. Etsy has a versioned normalized-payload cache; eBay staging
is per-manifest materialization, not cross-batch canonical caching. Prior private
regression passed duplicate/replay/late-data and full54-node parity; this is not
proof that all large-input plans are optimal.

This slice adds model CTAS/ANALYZE and config/prepare/drop/finish-hook timings,
preserving transaction and quality semantics. Commit/wrapper and individual JSON
operations remain unitemized; this is not complete attribution yet. If justified
by subsequent profiles, materialize bounded raw-element projections once, then
normalize/validate in a dependent dbt model. Reuse deterministic results by versioned
input identity and rejoin every physical audit. Preserve invalid-input behavior
and fingerprint-sensitive array order. Extra tables/caches have IO/storage and
invalidation costs; do not add them on assumption alone.

## Parallel execution

`infra/dbt/profiles.yml` sets threads2. Normal dbt can schedule independent DAG
nodes after their parents finish. Live compiled `delta_runtime.build()` instead
executes model/test SQL sequentially in ONE transaction: dbt threads does NOT
parallelize this custom loop. Independent source builds are a different mechanism.

Uncommitted parent tables are invisible on another connection. Do not thread a
shared connection or blindly commit intermediate models. A parallel design needs
batch/source-private candidates, dependency/visibility barriers, failure cleanup
and last-good atomic publication. Fix dirty-bucket work and profile first; no
parallel-runner rewrite implemented here.

References: [dbt threads](https://docs.getdbt.com/docs/running-a-dbt-project/using-threads),
[PostgreSQL materialization](https://www.postgresql.org/docs/16/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION).

## Actual private acceptance2026-11-14

runtime/daily-scope-20261114-02.json PASS: old/new day scope, empty former day,
currency move, exact untouched-day lineage, empty tick, replay and late older-date
insert. Full dbt60nodes and all8business outputs match delta; mapping rebootstrap,
actual HTTP waves1/10/100, process kill/rollback/concurrent-source gates also PASS.
No main activation or900 requalification.

Website staging parity covers duplicates/NULL/cross-linked children, Unicode,
empty/missing arrays and repeated raw; invalid arrays preserve SQLSTATE22023.
Private100order/raw SELECT median current60.966ms versus historical correlated
baseline242.657ms. This is NOT an improvement measured against the previous turn's
already optimized staging. Materialization/commit/concurrency differ on main.
Actual node evidence now splits CTAS/ANALYZE; full new hook phases are stored in
delta_results, not fully exported by the current harness. No JSON-only CPU or
complete main overhead attribution claimed. Main release/bootstrap remains pending.
