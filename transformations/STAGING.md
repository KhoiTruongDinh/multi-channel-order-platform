# Website staging SQL checkpoint

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
