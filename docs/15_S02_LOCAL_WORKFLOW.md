# M08B stable local workflow contract

Daily workflow revised on2026-11-01: [live local sources](16_M08_LIVE_LOCAL.md).
The single-dataset activation/empty-scope/clock contract below is retained for
explicit replay only; it is NOT a prerequisite for live append-only generation.

Owner approved the temporary Vietnamese design on 2026-10-31. This contract
precedes dependent DDL. Existing S01 and isolated acceptance remain supported.

## Optional short generation window (2026-11-01)

Global `duration_minutes` is an integer1..527040, default300. Only missing/null/
empty global end_at uses resolved start_at plus this duration; explicit end_at
and channel date overrides retain precedence. Concrete dates are persisted once.
The manual quick_6min.json sample uses six minutes and15..30s causal transitions;
it changes no schema, source contract, polling schedule or existing dataset.
Generation duration is not an end-to-end deadline. Daily use remains one stack;
no extra PostgreSQL, volume switch or automatic data reset is introduced.

## Ownership and activation

One ordinary local Compose stack, stable .env credentials and host ports; no new
PostgreSQL/Airflow for manual generation. Manual preparation is additive only:
unique dataset name -> SHA256 first12 hex campaign ID, refusing existing IDs.
Source APIs remain HTTP-only to ingestion; Website remains read-only SQL.
Generator/config live in tools/s02_data. No generation on container startup/GET.

Preparation creates marketplace rows, Website plans and references, not warehouse
answers. Mapping load is additive/idempotent with exact-content checks. No reset,
volume deletion, credential rotation or S01/S02 mixing is automatic. Activation
requires empty website orders/warehouse raw and current data on a first dataset;
otherwise refuse and require a separately approved data-retention transition.
Website catalog/customer references are inserted additively during prepare;
existing differing reference rows are rejected, not overwritten. Website orders
remain in the prepared timeline until explicit source playback applies them.

Materialize due initial Website transactions and signed notifications before
enabling polling. A successful empty first poll may advance its watermark;
later inserting older planned source timestamps beyond the overlap is not
automatically recovered. The finite acceptance runner enforces a source-warmup
barrier while DAGs remain paused, then enables schedules once. This does not
relax observation-only history or certify arbitrarily slow source drivers.

## Physical additions in marketplace_sim.s02

Reuse campaigns/orders/components/versions/deliveries from001 unchanged. Add:

| Table | Columns / constraints |
| --- | --- |
| local_datasets | campaign_id TEXT PK/FK campaigns(id); name TEXT unique nonblank; state TEXT LOADING/READY; references JSONB object; coverage JSONB object. READY only after source generation and mapping load; LOADING never served |
| website_versions | campaign_id FK local_datasets; order_id TEXT; sequence INTEGER>0; visible_at TIMESTAMPTZ; payload JSONB object; PK(campaign_id,order_id,sequence), UNIQUE(campaign_id,order_id,visible_at); index(campaign_id,visible_at) |
| playback | singleton BOOLEAN PK CHECK true; campaign_id FK local_datasets; mode realtime/replay; logical_start TIMESTAMPTZ; real_start TIMESTAMPTZ; stopped_at TIMESTAMPTZ nullable. Logical T=wallclock for realtime, else logical_start+(wallclock-real_start); stopped_at freezes T. One active dataset per stack |

Website plans/references are test-support storage, never collector access. New
rows follow immutable-after-ready triggers except playback control. Simulator
source reader roles may SELECT playback/local_datasets metadata, not Website
payloads. Legacy campaigns without local_datasets continue using wallclock.

## Clock and checkpoints

The eBay simulator exposes an authenticated local-only `/s02/clock` extension,
returning campaign ID, logical T, configured initial bound and running status;
no order payload, reference ledger or storage credential is exposed. Opt-in
polling reads that HTTP clock, fixes each cycle bound, and persists its actual
bound before acquisition; retries reuse the stored bound. API as-of reads,
Website writer and Etsy sender use the same PostgreSQL playback control.
Operational observations/leases/signatures/timeouts remain actual UTC.
Replay is1x, past/present only; no backwards restart or dataset change with
retained checkpoints. Explicit new/reset disposable scope is a later operator
decision, never an automatic cleanup. Airflow scheduler uses actual time.

## Generator

JSON workload files (stdlib, no host YAML dependency), three independently
configured channels: exact orders, optional range/timezone override, peak-hour
weights, basket bounds, branch weights/delays and required case counts. Order
and event seeds are separate; absent seeds are chosen once and persisted.
Global omitted/null/empty start_at defaults to actual prepare-time validation
UTC instant (whole seconds); end_at defaults to that resolved start+5 elapsed
hours. Explicit dates take precedence; per-channel omitted dates inherit the
individual global values. Resolved dates/seeds persist in config/manifest and
are never recomputed by playback. Complete parameter reference:
[tools/s02_data/CONFIG.md](../tools/s02_data/CONFIG.md).
Peak sampling uses duration*weight segments, not per-second arrays. Per-order
SHA256-derived streams isolate channels and event/purchase randomization.
Coverage quotas reserve feasible orders before random assignment, and fail when
unsatisfiable. Event timestamps advance causally and never exceed exclusive end.
Normal/coverage/faults distinguish valid baseline, required cases and opt-in
delivery/mapping faults. Unsupported API/security/crash fault plans are explicitly
marked planned/manual or unsupported, not reported as executed PASS. C/D retain
their broader recovery/load acceptance gates.

## Verification gates

Offline deterministic configuration/peaks/order and event separation/lifecycle/
coverage tests; source storage and roles on a fresh disposable case; realtime
and replay clock boundaries; complete manual prepare/inspect; fixed local Compose
configuration; original S01/guard regressions. Real scheduled/replay acceptance
must be recorded separately from code generation, with exact not-run gates.
