# M08D build/test timing review: historical unchanged900

Follow-up implementation2026-11-14: affected-day daily scope/publisher and new
subphase timers are described in24_ACTIVITY_TIME_REVIEW.md; private acceptance
in STATUS. Historical900 measurements below remain unchanged. No new main900
or production speedup has been measured after that correction.

Reviewed: 2026-11-14. This is evidence analysis and a proposed optimization order,
NOT a new load run, collector implementation or ten-second certification.

## Evidence and reproducibility

Campaign: `campaign-55425905726c48c880d022e0fbface94`, dataset
`campaign-rate-900-8eab0dfd3312`. Saved campaign report:
`runtime/campaign-55425905726c48c880d022e0fbface94/report.json`.
Actual build window: 2026-11-13 14:52:56.547078Z..15:04:46.054387Z.

Read historical `ops.execution_measurements`, `ops.delta_results`, task attempts
and batch membership using [inspect_build_900.sql](../tools/s02_data/inspect_build_900.sql).
The SQL uses READ ONLY and matches successful nonbootstrap attempts by batch AND
attempt number. Results: 35 complete stages (Website11/eBay6/Etsy18), 385 model
timings and208 test timings. Stage p50/p95 exactly reproduce saved campaign values.
Percentiles use PostgreSQL percentile_cont, not nearest-rank. The campaign's
source-eligibility delay statistic uses a different clock and percentile method.

Local evidence export: `runtime/build900-review-20261114.json` (ignored runtime,
not a committed fixture). Queries do not replay business SQL or regenerate data.
This review covers concurrent retained-stack work in the window, not exclusively
the900 new orders. There were7579 prior orders before admission; each source got
300 new orders. A stage processes an affected subset plus relevant observed
context, not all900 as one isolated batch.

PostgreSQL was initially stopped. Owner authorized starting ONLY PostgreSQL for
read-only queries and stopping it afterward. No Airflow/SIM started, no pipeline
executed, no intentional business-data mutation, no reset or volume deletion.
Initial pg_isready briefly returned no response during startup; subsequent check
accepted connections and SELECTs passed. Final container state: exited, code0;
`docker ps` empty, matching the initial stopped-stack state.

Reproduce when PostgreSQL is intentionally running, from repo root, PowerShell:

```powershell
Get-Content tools/s02_data/inspect_build_900.sql -Raw -Encoding UTF8 |
  docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=30000' multi-channel-order-platform-postgres-1 psql -X -qAt -v ON_ERROR_STOP=1 -U postgres -d data_platform
```

Do not start other services merely to read retained historical timings.

## Whole-stage timings, seconds

| Source | Samples | p50 | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| ebay_sim | 6 | 2.641 | 3.797 | 4.080 |
| etsy_sim | 18 | 4.982 | 6.916 | 8.066 |
| internal_web | 11 | 1.842 | 6.971 | 7.895 |

A p95 below5s is not MAX below5s. Website and Etsy exceed5s, and this is not yet
a satisfactory proof of the owner's collect-to-publication MAX<=10s target.

## What the runtime actually does

The opted-in warm path executes dbt SQL compiled at deployment; it does NOT start
a fresh dbt CLI/full54-node project for each cycle. See
[delta_runtime.build](../transformation/delta_runtime.py).

1. Validate compiled plan/source hash and mapping release; check batch/attempt.
   Source validation traverses and hashes relevant project files; it is not a
   zero-cost cached constant. Correctness must not be removed to gain speed.
2. Mark BUILDING, commit that operational transition; set transaction-local JIT
   off and batch context.
3. Run prepare hook (Etsy cache population/guard; other sources a trivial hook).
4. Drop prior source-private candidate tables in reverse dependency order.
5. For each of11 source-local models, CREATE TABLE AS compiled SQL, then ANALYZE.
6. Run applicable tests sequentially (Website14/eBay3/Etsy2), count violations.
7. Run finish hook (Etsy mapping-exception persistence), store passing node results,
   mark TESTED and commit. A failure rolls back build changes and records failure.
8. Workflow telemetry includes wrapper state/audit DB work around the build call.

A model timer covers CTAS + ANALYZE + client/server elapsed time, not pure SELECT
CPU time. Test timers cover executing the compiled violation query. Drops, hooks,
configuration validation, operational transitions and commits are NOT individually
timed in the retained node ledger. Source-slot waits have their own telemetry;
do not automatically put them inside build time or call residual time lock wait.

## Mean per-stage decomposition, seconds

| Source | Timed models | Timed tests | Unitemized remainder |
| --- | ---: | ---: | ---: |
| ebay_sim | 2.359 | 0.225 | 0.139 |
| etsy_sim | 1.540 | 0.046 | 3.653 |
| internal_web | 2.890 | 0.036 | 0.197 |

Remainder = stage duration minus the model/test timers FOR THE SAME attempt.
These mean components are additive; separately computed p95 components are not.
Remainder is not proof of Python overhead, network time, lock time or cache cost.
Etsy's remainder accounts for about69.7% of its aggregate successful build time.
Hooks/configuration/drop/commit/waits require subphase instrumentation to attribute it.

Important examples:

- Etsy batch `844fd5ce-3422-5be2-984a-51b6a412fe2e`:66 affected orders,
  101 new raw/123 total context raw; stage8.066 = models3.044 + tests0.047 +
  remainder4.975 seconds.
- Etsy EMPTY batch `3dce978f-5ce5-56d3-84c7-870266febcc2`: zero affected orders,
  zero new/context raw; stage6.607 = models0.908 + tests0.019 + remainder5.679.
  This rules out 'too many new orders' as a sufficient explanation. It does NOT
  prove which uninstrumented operation caused the delay.
- Website batch `d76c852c-5a69-5028-8c24-1a8ff1892417`:79 affected orders,
  one new window raw/three context raw; stage7.895 = models7.405 + tests0.059 +
  remainder0.431. Product activity model alone took5.061 seconds.

## Model breakdown

| Source | Model | Mean seconds | p95 seconds | Max seconds |
| --- | --- | ---: | ---: | ---: |
| ebay_sim | `ebay_candidate_product_activity_daily` | 0.799 | 1.261 | 1.276 |
| ebay_sim | `stg_ebay_observations` | 0.752 | 0.934 | 0.940 |
| ebay_sim | `ebay_candidate_order_line_snapshot_history` | 0.178 | 0.339 | 0.372 |
| ebay_sim | `ebay_candidate_order_status_current` | 0.154 | 0.459 | 0.584 |
| ebay_sim | `ebay_candidate_snapshot_evidence` | 0.139 | 0.220 | 0.225 |
| ebay_sim | `ebay_candidate_order_activity_daily` | 0.122 | 0.229 | 0.257 |
| ebay_sim | `ebay_candidate_order_snapshot_history` | 0.066 | 0.112 | 0.118 |
| ebay_sim | `int_ebay_versions` | 0.063 | 0.102 | 0.105 |
| ebay_sim | `ebay_candidate_order_lines_current` | 0.042 | 0.088 | 0.104 |
| ebay_sim | `ebay_candidate_orders_current` | 0.025 | 0.052 | 0.061 |
| ebay_sim | `ebay_candidate_source_health` | 0.019 | 0.033 | 0.037 |
| etsy_sim | `etsy_candidate_product_activity_daily` | 0.730 | 1.441 | 1.576 |
| etsy_sim | `etsy_candidate_order_line_snapshot_history` | 0.161 | 0.402 | 0.606 |
| etsy_sim | `stg_etsy_observations` | 0.156 | 0.311 | 0.492 |
| etsy_sim | `int_etsy_versions` | 0.091 | 0.353 | 0.389 |
| etsy_sim | `etsy_candidate_order_status_current` | 0.087 | 0.236 | 0.347 |
| etsy_sim | `etsy_candidate_source_health` | 0.076 | 0.129 | 0.254 |
| etsy_sim | `etsy_candidate_order_activity_daily` | 0.073 | 0.149 | 0.161 |
| etsy_sim | `etsy_candidate_snapshot_evidence` | 0.060 | 0.138 | 0.272 |
| etsy_sim | `etsy_candidate_order_snapshot_history` | 0.058 | 0.142 | 0.174 |
| etsy_sim | `etsy_candidate_order_lines_current` | 0.028 | 0.061 | 0.073 |
| etsy_sim | `etsy_candidate_orders_current` | 0.022 | 0.047 | 0.062 |
| internal_web | `candidate_product_activity_daily` | 1.449 | 3.814 | 5.061 |
| internal_web | `stg_website_observations` | 0.655 | 1.310 | 1.523 |
| internal_web | `candidate_order_line_snapshot_history` | 0.221 | 0.634 | 0.636 |
| internal_web | `candidate_order_status_current` | 0.155 | 0.487 | 0.596 |
| internal_web | `candidate_order_activity_daily` | 0.145 | 0.383 | 0.420 |
| internal_web | `candidate_order_lines_current` | 0.070 | 0.168 | 0.172 |
| internal_web | `int_website_versions` | 0.057 | 0.143 | 0.211 |
| internal_web | `candidate_order_snapshot_history` | 0.039 | 0.090 | 0.092 |
| internal_web | `candidate_snapshot_evidence` | 0.036 | 0.106 | 0.166 |
| internal_web | `candidate_orders_current` | 0.033 | 0.096 | 0.156 |
| internal_web | `candidate_source_health` | 0.030 | 0.048 | 0.053 |

For tests, mean total time per stage is only0.036s Website,0.225s eBay and0.046s
Etsy. The largest test is eBay fulfillment integrity (mean0.204s/p950.442s,
max0.514s); Website constraints mean0.010s/max0.021s; Etsy constraints mean0.043s/
max0.162s. Removing required tests is not the supported optimization here.

Candidate output row counts do not describe all rows read. For example the
Website slow product-activity output had166 aggregate rows, but its input SQL
combines retained current order/line sets with affected candidates.

## Why product activity deserves review

All three product-activity models join `effective_current` order and line sets,
then GROUP BY date/product/mapping/currency. In delta mode that macro unions
untouched retained core rows with the affected candidates. This avoids rebuilding
every order snapshot but still computes effective source-wide aggregates each cycle.

Thus 'only900 orders' or 'only166 output rows' does not mean the query touches only
900 or166 rows. The models also pay CTAS/ANALYZE/materialization costs. The observed
times identify where to inspect, but no new EXPLAIN/BUFFERS was run in this task:
join strategy, IO, spills, contention and statistics are not established causes.

## Does changing collect affect build/test?

YES, physical inputs and evidence change; business semantics must not.

Etsy recovery page raw has many receipts, unlike current eligible single
`etsy_receipt` raw. Update eligibility/route, element identity/cache inputs,
staging and lineage together. No fabricated detail acquisitions or successful
HTTP attempts. Preserve acquired timestamps, fingerprints, independent states,
money grain, mapping version, and observed-only history. Matching page raw only
by byte hash would conflate receipts and is forbidden.

A complete receipt page can remove redundant HTTP while still increasing parsing
per raw envelope. Fewer requests do not prove faster build. Measure page expansion,
cache hit/miss and input/context cardinality after the change. Full-dbt and compiled
paths must match on the same new frozen inputs; regenerate/version/bootstrap plans
before live activation. Applicable tests cannot be bypassed because transport changed.

## Recommended optimization order (proposal, not implemented)

1. **Instrument the missing time first.** Separate plan/source/mapping validation,
   prepare/cache fill+guard, candidate drops, each CTAS vs ANALYZE, finish exceptions,
   result/audit writes and commits. Capture matching row counts, lock waits and
   cache hit/miss. Keep total stage telemetry and attempt identity unchanged.
   Etsy's70% remainder is the largest unexplained area, even for an empty batch.
2. **Profile product activity across all sources.** Use bounded EXPLAIN
   (ANALYZE, BUFFERS, SETTINGS) on SELECT equivalents in a safe test scope with
   matching retained history/concurrency. Inspect effective-current joins and
   stats. Consider materializing/indexing reusable effective sets once, or
   recomputing only dirty date/product/currency buckets using old AND new keys.
   An order changing/removing a line must update its former bucket too.
   Do not move dbt-owned business SQL into Python or blindly add indexes.
3. **Design a no-business-change tick.** Empty affected sets should not rebuild
   every business candidate/aggregate solely to refresh health. Preserve health,
   successful acquisition/checkpoint/audit, mapping/code-release behavior and
   durable raw consumption. This is a separate tested design, not an unconditional
   early return when new raw count=0.
4. **Then reduce demonstrated fixed overhead.** If timings identify drops/ANALYZE
   or repeated source hashing as material, qualify reusable staging/materialization
   and release-aware validation. Do not remove ANALYZE, fsync, quality gates or
   source/mapping drift guards on assumption alone. Preserve rollback and stale-plan
   refusal. Parallel models are not the first change on the measured2CPU/4GB stack.

Collector payload reuse and subphase instrumentation can be implemented as small
reviewable slices; compare the SAME900 afterward without increasing budgets.
Publish tuning is deferred per owner request. Its observed saved p50/p95 is
Website0.866/3.183s, eBay0.844/1.965s, Etsy0.692/2.072s. These are whole-stage
times, NOT evidence that transmission/network is responsible; global publication
lock, metadata/config checks, SQL, WAL/commit and audit all remain possible costs.

## Not run / not claimed

No new900/burst/soak, no new EXPLAIN/BUFFERS, no new SQL benchmark, no collector/SIM
implementation, no release/bootstrap or S01 DB regression in this docs/report task.
Subphase causes remain unmeasured. No stage/commit/push. Full M08D and MAX<=10s
remain pending.
