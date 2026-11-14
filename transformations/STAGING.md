# Staging reuse and SQL checks

M08D2026-11-14 daily correction: activity_scope/daily_orders helper models bound
retained-current aggregation and publication to old/new affected UTC creation
days, without changing the report metric to receipt time. New runtime node timers
separate CTAS from ANALYZE; config/prepare/drop/finish timings expose more of the
previous remainder. Commit/wrapper/individual JSON operations are still not fully
attributed. Existing materialized staging and canonical identities remain intact.
The private harness includes Website staging multiset/fingerprint parity on
duplicates, NULL/cross-linked children, Unicode, empty and invalid arrays; actual
results are in STATUS, not inferred from SQL style.

Owner SQL-style cleanup2026-11-14: see [SQL_STYLE.md](SQL_STYLE.md) for explicit
consumer projections, COUNT(1), explicit INNER JOIN and GROUP BY deduplication,
plus index/filter limitations and compiled-plan release gates. These edits are
not a new execution-plan or load-performance result.

Plan-driven eBay evidence rewrite: `ebay_candidate_snapshot_evidence.sql` uses
three keyed evidence paths and expands each relevant raw list page once. Final
GROUP BY retains the old OR/EXISTS deduplication semantics; every manifest/acquisition link
remains. No stable schema, fingerprints or publication policy changes. Run
`python tests/ebay_evidence_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/ebay-evidence-review.json`
for rollback-only full-row parity and bounded execution plans. Details and scope:
`docs/20_M08D_REUSE_COORDINATION.md`; actual deployment/results are in STATUS.

Etsy follow-up2026-11-12: `models/etsy/stg_etsy_observations.sql` now reuses its
canonical payload from `cache.etsy_payloads`, filled by a transactional dbt
pre-hook for missing scoped byte hashes/code versions only. A MATERIALIZED CTE
avoids duplicate normalization within the miss set. Every frozen raw acquisition
is joined back, including repeated observations. It does not change the canonical
functions, raw columns, filters, errors or fingerprint. Apply migrations010/011
through normal bootstrap/migrate/live-up before running the updated full project.
Reproduce the opt-in disposable SQL probe (Docker only; no main services needed):

```powershell
python tests/etsy_staging_probe.py --report runtime/etsy-staging-review.json
```

The probe creates/removes only its uniquely labeled, network-disabled PostgreSQL
container with tmpfs data and no host ports or volumes. See STATUS for exact
results. Its benchmark is the warm-cache SELECT only, excluding cold population,
pre-hook/DDL and full workflow costs. It is NOT whole-pipeline speedup or capacity.
This diagnostic does not replace full dbt/release/load acceptance.

The Website staging model expands/group child arrays once per raw acquisition
and order, then joins them to headers. Source ordinality, duplicate evidence,
raw/source/account scope and canonical fingerprints remain unchanged. Shipment
membership uses distinct raw/order/shipment links to preserve EXISTS semantics.
Statement-local materialized CTEs prevent repeated shipment-item expansion.

Website staging/intermediate relations are dbt tables rebuilt per batch, not
incremental caches. The frozen input manifest, complete model/test gate and
atomic publication remain required. This optimization does not change the
approved source or stable warehouse schema.

## Reproduce SQL parity and profiles

From repository root with an existing local Airflow project environment and
PostgreSQL running:

```powershell
python tests/website_staging_probe.py --container multi-channel-order-platform-airflow-1 --report runtime/website-staging-review.json
```

Choose a new report path; existing evidence is never overwritten. The host
runner uses only Python standard library and sends current SQL/fixtures to the
container's project venv. It compares every staging output column/fingerprint
against [the frozen pre-optimization SELECT](../tests/sql/website_staging_before.sql)
using bidirectional EXCEPT ALL, plus independent payload/hash assertions.

Checks cover S01, empty/missing child arrays, duplicates, repeated acquisitions,
shipment membership, Unicode and invalid arrays. Up to200retained raw rows are
copied into session-temp storage. Single-raw profiles use1/10/100/300/600orders,
four alternating EXPLAIN ANALYZE samples each. All temporary writes roll back;
no scheduler, shared build or warehouse mutation. See STATUS for exact outcomes.

An isolated SELECT speedup is not pipeline capacity, sustained load acceptance
or a guarantee that all planned intermediate source states were observed.
