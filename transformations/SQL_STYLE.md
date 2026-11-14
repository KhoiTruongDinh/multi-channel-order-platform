# Authored dbt SQL conventions and review boundaries

Owner-requested M08D cleanup, 2026-11-14. These are readability/projection rules,
not a claim that changing spelling proves faster execution. Business output,
source fingerprints, audit lineage and observed-history rules remain fixed.

- Use explicit needed columns; no SELECT wildcard or qualified alias wildcard.
  Intermediate staging no longer carries unused raw bytes/HTTP metadata into
  normalization. Raw storage itself is unchanged. `effective_current` callers
  specify a projection shared by both sides of the retained/candidate UNION ALL.
- Use COUNT(1) consistently in authored SQL. This counts rows like COUNT(*), not
  like COUNT(nullable_column); it is not an established speed optimization.
- Spell implicit inner joins as INNER JOIN. Keep LEFT and CROSS/LATERAL semantics;
  converting a LEFT JOIN to INNER JOIN can silently drop unmatched evidence.
- Deduplicate with GROUP BY at the same grain. Keep IS DISTINCT FROM: it is a
  NULL-safe comparison, NOT DISTINCT-row elimination. Aggregate DISTINCT checks
  are rewritten as grouped inputs while preserving excluded SQL NULL values.
- EXISTS uses SELECT1. PostgreSQL already stops once existence is determined;
  no TOP(1), no pointless extra LIMIT1 is required. Do not replace existence with
  COUNT(1)>0. Scalar top-row queries use ordered LIMIT1 where actually required.
- Remove trivial SELECT-wildcard wrapper CTEs, not CTEs indiscriminately. Keep
  MATERIALIZED boundaries that avoid repeated JSON-array expansion/normalization.
  CTE count alone does not establish a bad execution plan. Preserve array ordering
  when business-payload fingerprinting depends on it.
- Restrict acquired input by frozen batch/source/resource and runtime affected
  keys where applicable. Do not add arbitrary LIMIT/latest-only filters that
  drop observed history or omit retained rows required for aggregate correctness.

## JOIN/filter and declared-index review

This task inspects repository DDL and SQL, not installed main-catalog coverage or
new EXPLAIN/BUFFERS results. No indexes/migrations are added speculatively.

| Relationship | Declared coverage / limitation |
| --- | --- |
| Frozen inputs to raw | ops.batch_inputs PK(batch_id,raw_record_id); raw.raw_records PK(raw_record_id). Filter batch first. |
| Raw to acquisition run | ops.pipeline_runs PK(run_id). This does not provide an index for every raw-side run/metadata predicate. |
| Dirty-key membership | ops.delta_batch_keys PK(batch_id,source_order_id); delta_raw_order_idx covers scoped source/order routing. |
| Existing current order identity | core.orders_current PK(source_system,source_account_id,source_order_id); corresponding leading identity prefix in line PK. |
| Snapshot to lines/evidence | History/snapshot PKs; order_lines_snapshot_fk_idx added in012 for current-line snapshot joins. |
| Etsy canonical cache | Composite PK(source_system,source_account_id,byte_sha256,normalization_version), matching lookup. |
| Product mapping | Active confirmed partial expression indexes exist. The OR of listing/variant and SKU conditions is NOT proof of complete efficient index coverage. Evaluate plans/cardinality before another index. |
| Parsed JSON / CTE / private CTAS | No automatic permanent indexes on derived JSON elements or freshly built candidate tables. Explicit equijoins help readability but do not guarantee an indexed plan. |

Potential hotspots still needing execution-plan evidence: product-activity joins
over effective retained current sets; raw metadata order-parent linkage; mapping
OR predicates. A sequential/hash plan can be appropriate for a small set. Do not
force nested-loop/index access or create an index for every ON expression.

## Checks and release

`python -m unittest -v tests.test_dbt_sql_style tests.test_delta_plan` guards
authored SQL style/projections and stale-plan refusal. dbt-generated built-in
tests may use their own upstream SQL conventions; this policy covers repo-authored
models/macros/tests, not generated artifacts.

`python tests/delta_runtime_probe.py --docker --report runtime/sql-style-review.json`
runs the existing disposable PostgreSQL/dbt semantic, rollback and full-project
parity harness. Actual results, failures and unrun checks belong in STATUS.

2026-11-14 evidence: runtime/sql-style-delta-20261114-final.json PASS; full54-node
dbt parity across all8business outputs, plus actual collector waves1/10/100,
duplicate/late/empty data, process kill/rollback and concurrent-source gates.
This is neither main900 requalification nor scheduled Airflow acceptance.

Model/macros edits change source and normalization/compiled-plan hashes. Existing
deployed plans must refuse a changed source tree. Recompile, verify full-dbt parity
and explicitly bootstrap a new release before main activation; do not edit plan
hashes or disable validation to make a stale plan execute. This task does not
activate a release, implement collection changes or rerun900.

References: PostgreSQL16 [EXISTS](https://www.postgresql.org/docs/16/functions-subquery.html),
[CTE materialization](https://www.postgresql.org/docs/16/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION).
