# Target field dictionary and storage contract

## M08D bounded daily activity scope (finalized2026-11-14, before models)

Daily order/product marts retain UTC SOURCE-CREATED cohort meaning, not processing
throughput. Pipeline attempts use actual execution time; observed-version activity
uses version observation time and must not be labeled sales/new-order revenue.

New source-private dbt helper relations `candidate_activity_scope` and
`candidate_daily_orders` (with eBay/Etsy prefixes), not new stable warehouse tables:

| Relation | Columns / constraints |
| --- | --- |
| activity scope | activity_date DATE!, source_system TEXT!, source_account_id TEXT!, batch_id UUID!; unique date/source/account for the exact frozen batch. Union old current dates of affected orders and new candidate dates. Bootstrap additionally covers existing daily-mart dates to remove stale empty buckets. No CURRENT_DATE filter. |
| daily orders | source_system/account/order TEXT!, source_created_at TIMESTAMPTZ!, currency TEXT!, source_order_total_amount NUMERIC(20,6) nullable. Unique scoped order; effective current rows restricted to the explicit scope's UTC half-open day ranges. |

Publish reconciles daily mart rows ONLY inside this scope, preserves untouched
dates, and handles scoped buckets that become empty. Product/currency/mapping
buckets within a touched day are recomputed together; day scope is deliberately
coarser than individual product keys. Status-current remains source-wide.
Dictionary/schema/fingerprints of existing stable outputs and S01 remain unchanged.

## M08D delta fields (finalized2026-11-13, BEFORE migration012)

Coordinator integration uses existing polling_cycles.settings JSON: optional
delta_plan_sha256 TEXT value, exactly64lowercase hex, immutable with the cycle's
mapping/transformation versions. Absent means legacy; retries never switch modes.
No new DDL. Freeze TRANSFORM and publication PUBLISH pipeline_runs retain the
actual airflow_dag_id/airflow_run_id pair; publication status commits with release.

Contract/design:21_M08D_DELTA_RUNTIME.md. Existing core/mart column definitions
and source-version IDs are unchanged. Last-recomputed row lineage can differ
from the latest source publication pointer; atomic consistent reads remain valid.

| Relation / grain | Columns and constraints |
| --- | --- |
| ops.delta_raw_keys / one raw/order link; NULL order marks an empty page | raw_record_id UUID NOT NULL FK raw; source_system/source_account_id TEXT NOT NULL nonblank; source_order_id TEXT nullable, nonblank if present; UNIQUE NULLS NOT DISTINCT(raw_record_id,source_order_id). Immutable INSERT-only derived routing; index(source_system,source_account_id,source_order_id,raw_record_id). |
| ops.delta_batches / one opt-in transform batch | batch_id UUID PK/FK transform_batches; source_system/source_account_id TEXT NOT NULL, one of the3supported tuples; plan_sha256 TEXT lowercase64hex; build_schema TEXT fixed by source to build_delta_web/ebay/etsy; base_batch_id UUID nullable FK transform_batches; bootstrap BOOLEAN NOT NULL; expected_nodes JSONB NOT NULL object with model/test ID arrays; registered_at TIMESTAMPTZ NOT NULL actual clock. Immutable. |
| ops.delta_new_inputs / exact unseen raw frozen for a batch | batch_id UUID,raw_record_id UUID, composite PK/FK ops.batch_inputs; immutable. Distinct from historical evidence also in batch_inputs. |
| ops.delta_batch_keys / frozen affected order keys | batch_id UUID FK delta_batches,source_order_id TEXT NOT NULL nonblank; composite PK. Source/account come from the parent. Immutable. |
| ops.delta_seen_raw / consumption only on successful publication | plan_sha256 TEXT lowercase64hex,raw_record_id UUID FK raw,processed_batch_id UUID FK delta_batches; PK(plan_sha256,raw_record_id); recorded_at TIMESTAMPTZ NOT NULL actual clock. INSERT-only; trigger requires matching plan and PUBLISHED batch, exact membership in delta_new_inputs. No consumption on failed builds/transactions. |
| ops.delta_results / durable gate attempt evidence | batch_id UUID FK delta_batches,attempt_number INTEGER1..5; composite PK; plan_sha256 TEXT lowercase64hex; passed BOOLEAN; results JSONB NOT NULL object of node IDs/status/duration, no source payload; recorded_at TIMESTAMPTZ NOT NULL actual clock. Immutable. A TESTED fast batch requires matching successful expected-node set. |

platform_owner owns the operational tables. platform_transform SELECT/INSERT on
routing/batch/key/result tables and SELECT seen; platform_publisher SELECT all and
INSERT seen only, plus read-only config.product_mapping for publication-time
configuration validation (config schema USAGE, no config writes). No PUBLIC/report
access. Three new build schemas grant transform
USAGE/CREATE and publisher USAGE/SELECT on transform-created candidate tables.
Transform receives read-only core tables for effective-state mart SQL. Add the
missing core.order_lines_current(snapshot_id) FK-supporting index; no field change.
No data reset, pointer deletion, TTL owner steal or automatic retry reset.

M08D ownership timing refinement2026-11-08 (existing columns; no DDL): when
freezing a DAG-owned transform batch, populate its TRANSFORM pipeline_run's
airflow_dag_id/airflow_run_id together in the SAME transaction that exposes
FROZEN and batch_inputs. Use the actual Airflow owner run, not the derived
polling execution ID. Both values absent remains valid for direct/manual CLI;
reject a partial pair. Finally-time lineage annotation remains for other child
runs, but must not be the first owner assignment of an exposed transform batch.

Status: M01 accepted technical direction, 2026-10-25. This is the target
warehouse/operational contract; the source exports in `docs/contracts/` remain
the approved source-facing contract and are not replaced by this document.

M03 implementation, 2026-10-26: candidate relations use the same column order,
types and grains as the published tables; no target-column migration was needed.
Snapshot UUIDs are deterministic hashes of source/account/order, original source
update representation and source content fingerprint, excluding mapping and batch
versions. The SHA-256 fingerprint canonicalizes the six website order/child arrays
with sorted object keys and preserved array order, matching `website_order` in the
fixture utility. Evidence retains each raw ID and its original byte checksum.
`mart.source_health.coverage_state` remains UNKNOWN until continuity can be proven.

M04 reuses the existing operational columns and constraints; no target DDL was
required. One `RECOVER` pipeline run with stream `website_workflow` represents a
bounded workflow/recovery cycle, alongside its actual acquisition/transform/publish
child runs. Its UUID derives from the explicit execution ID. Task attempt UUIDs
derive from execution/stage/attempt, with unique `(run_id, task_name, attempt_number)`.
The controller allocates at most five attempts per stage while locking the parent
row; Airflow retries/clears never reset this count. RUNNING interruptions consume
their existing attempt. Airflow DAG/run IDs and stable batch IDs link these audits.

## Conventions

M06 finalized operational extension (2026-10-28, before migration 005):

- `ops.processing_work.lease_token UUID ?`: ownership/fencing token; for
  `ETSY_RECEIPT` work, LEASED requires a token and other states require null.
  Claim/reclaim atomically increments the existing 0..5 cycle_attempts and assigns
  a new token/deadline. Completion requires the current token and unexpired lease.
  Expired attempts remain audited; no scheduled reset of exhausted counters.
  An Etsy work trigger forbids counter decreases and changes to cycle identity.
- `ops.etsy_work_context`: `work_id UUID ! PK/FK processing_work`,
  `run_id UUID ! FK pipeline_runs` (receipt acquisition), `resource_url TEXT !`,
  `cycle_id TEXT !` nonblank (inbox identity or explicit recovery/replay identity).
  Context is immutable. One inbox message creates one work item; recovery work
  dedupe is cycle + receipt. Explicit replay creates new work/context, retaining
  previous work/attempts. No DELETE grant or mutable context to reset a cycle.
  `replay_of_work_id UUID ? FK processing_work` explicitly links a controlled
  replay to the failed work it supersedes. Recovery refuses to enqueue a fresh
  cycle for a receipt with unresolved FAILED work; only a successful linked
  replay clears that gate. A scheduled tick cannot reset an exhausted work budget.
- `ops.etsy_http_attempts`: `attempt_id UUID ! PK`, `work_id UUID ? FK`,
  `run_id UUID ! FK pipeline_runs`, `lease_token UUID ?`, `attempt_number INTEGER !`
  1..5 for work requests, `raw_record_id UUID ! FK raw_records`,
  `recorded_at TIMESTAMPTZ !`. Append-only ingest grants; each HTTP result retains
  exact bytes/status and actual fetch time even after lease loss. Raw acquired_at
  may use an explicit S01 observation clock, separately labeled in metadata.
  `collection_run_id UUID ? FK pipeline_runs` links the invoking drain/recovery
  acquisition cycle (and thus its Airflow parent), separately from the receipt
  work run. New CLI writes populate it; earlier development/test rows may be null,
  without invented backfill. Work-attempt log references and raw metadata mirror
  that link. Finalized before adding the column during this uncommitted migration.
- Existing raw/run/inbox/delivery/work columns retain their types and keys.
  Receiver request run + raw + inbox + delivery + work/context commit atomically
  before 2xx; rejected deliveries retain audit/raw when the DB is available.
  Receiver DB failure returns 503, with no claim that unavailable DB persisted
  rejection audit. Subscription/shop come from configured trusted context.
- Existing polling-cycle configuration protects scheduled Etsy recovery windows
  and windowless inbox-drain context (null start/end). The latter uses no fake
  extraction window. Recovery streams `receipts` (explicit historical replay)
  and `receipts_polling` (current clock) stay separate; inbox stream is `inbox`.
  Scheduled acceptance uses explicitly isolated `receipts_test_<32 hex>` streams
  so reruns can cover the fixed historical receipt without rewinding live state.
  The selected stream is bound in immutable cycle settings and restored afterward.
- Etsy receipt=order, transaction=line, source/account `etsy_sim`/`7001`.
  Target core/mart types/columns remain unchanged; only receipt HTTP resources
  from completed acquisitions enter manifests. Notifications never become order
  snapshots. SQL owns Money division, product mapping, fingerprint/history/state.
  Unknown mapping retains the line plus an operational warning exception.
  One physical receipt request has an append-only `etsy_http` audit body and,
  only after fencing succeeds, an `etsy_receipt` admission copy with identical
  bytes/hash and a pointer to the HTTP raw ID. This is not a second fetch or an
  invented source state. Count physical requests via `etsy_http_attempts`, not
  by summing every raw resource type; stale-owner HTTP audit is never admitted.

M05B finalized operational extension (2026-10-28):
`ops.polling_cycles` has `run_id UUID ! PK/FK ops.pipeline_runs`,
`validation_mode TEXT !` constrained to runtime, `clock_mode TEXT !` constrained
to current, `mapping_version TEXT !`, `transformation_version TEXT !`,
`overlap_seconds INTEGER !` >=0, and `settings JSONB !` constrained to an object.
Source/account, DAG/run identity and immutable requested window are inherited
from the parent run. Application roles may insert/read cycles but never change
their configuration; a trigger rejects UPDATE/DELETE. Same execution reuses the
parent window, even after its checkpoint advances. Settings bind test fault flags
so retry cannot change validation/fault semantics. Actual fetch time is current.

M08D pagination refinement (no DDL): marketplace cycles may additionally persist
`settings.page_size` as a JSON integer, eBay1..200 / Etsy1..100. Missing legacy
keys mean1. A retry restores the stored value, never the current environment;
new live cycles default50 via the live overlay, base/S01 commands default1.
Direct Etsy recovery refuses a different limit if this collection already has
retained list requests, preserving URL budgets and validated-page cache identity.

`ops.transform_batches.validation_mode TEXT ! DEFAULT 's01'` accepts s01/runtime.
The freeze command persists it; TESTED verifies artifact batch, source, mapping,
transformation and validation mode before promotion. Existing S01 commands retain
their default. Runtime keeps invariant tests, skipping only golden S01 assertions.
Polling uses `orders_polling` checkpoints and `orders` raw resources, preserving
existing historical `orders` checkpoints and source/account/version identities.
No business field changes. Global session coordination plus the existing active
batch guard spans complete polling releases and cooperating CLI freezes.

M05 target contract (2026-10-28, finalized before dependent models): no new DDL.
eBay uses source `ebay_sim`, account `seller_sim_01`; order/line identities remain
scoped. Raw resource kinds are `ebay_orders`, `ebay_order`,
`ebay_fulfillments`, and `ebay_fulfillment`. Each HTTP response (including errors)
retains exact bytes, status, sanitized headers, requested window and observation
time. Metadata links order ID and order-detail raw ID; no authorization is stored.
Durable `EBAY_ORDER_DETAILS` work is created from each saved page before paging;
its run-scoped dedupe key links the page raw ID. A window succeeds only after all
pages and required detail/fulfillment work succeed. Retry starts a new acquisition
run, retaining failed raw/work; processing uses successful frozen runs only.

The order content fingerprint is SHA-256 of the approved canonical order JSON:
sort object keys and known identity arrays (`lineItems`, `fulfillments`,
`transactions`), preserve all other array order and absent/null distinctions.
Fulfillment evidence has its own resource fingerprint and observation timestamp;
it never changes order source-version identity. Same-time conflicting order
content or incompatible fulfillment evidence blocks publication. First observed
time comes from actual retained order acquisition, not a synthesized source state.

eBay line gross is `lineItemCost.value` (already the entire line); derived unit
gross is line gross / quantity. Optional discount and tax remain null. Source
payment/fulfillment/cancellation enums remain separate. Common partial shipping
requires dated, in-order, non-overallocated line allocations and remaining units;
`IN_PROGRESS` alone remains `UNKNOWN`. No delivered/refund claim is derived.
Line `fulfillment_evidence` is an object containing the supporting fulfillment
objects; all acquisitions also link through `core.snapshot_evidence`.

M05 uses source-specific eBay candidates and `ebay_orders` publication, sharing
the existing global active-batch guard. Website candidates/publication and their
default commands remain unchanged. eBay releases delete/copy only eBay rows.

- `!` means `NOT NULL`; `?` means nullable. `PK`, `FK` and `UQ` name key roles.
- Common source identity is always scoped by `source_system ! TEXT` and
  `source_account_id ! TEXT`. A source order, line, SKU, or listing alone is
  never a global key.
- UUID values are generated by the writing application. PostgreSQL does not
  invent source identity. `TIMESTAMPTZ` values represent instants and are
  displayed as UTC by clients.
- Common amounts use `NUMERIC(20,6)` and an ISO-style three-uppercase-letter
  currency. Null means unavailable/not supported; it is distinct from zero.
- Raw source bytes and their 32-byte SHA-256 remain separate from parsed JSON.
  Source content fingerprints exclude acquisition metadata. Mapping and
  transformation versions remain separate.
- Source states are retained as text. Common payment, fulfillment, and
  cancellation states are independent columns; no combined lifecycle state is
  permitted.
- Stable `core`/`mart` tables are publication targets. Implemented dbt models
  build candidates in `build`; the publisher copies the selected source only
  after verified tests pass. There is currently no global cross-source release ID.

## Raw and operational fields

### `raw.raw_records` — one acquisition/delivery body

| Column | Type / nullability | Definition / constraint |
| --- | --- | --- |
| `raw_record_id` | UUID ! PK | Application-assigned acquisition identity. |
| `run_id` | UUID ! FK | Acquisition run in `ops.pipeline_runs`. |
| `source_system`, `source_account_id` | TEXT ! | Account-scoped source context; nonblank. |
| `resource_type` | TEXT ! | Contract resource/envelope kind; nonblank. |
| `resource_locator` | TEXT ? | Sanitized URL, table-envelope name, or equivalent. |
| `request_method` | TEXT ? | HTTP method or documented database-read method. |
| `request_window_start`, `request_window_end` | TIMESTAMPTZ ? | Requested interval; end requires start and cannot precede it. |
| `response_status` | INTEGER ? | HTTP-like status 100–599 where applicable. |
| `acquired_at` | TIMESTAMPTZ ! | Platform observation time. |
| `raw_bytes` | BYTEA ! | Exact response/webhook bytes or documented website envelope bytes. |
| `parsed_payload` | JSONB ? | Parsed representation; null when parsing failed/not applicable. |
| `byte_sha256` | BYTEA ! | Exactly 32 bytes, over `raw_bytes`. |
| `contract_version` | TEXT ! | Source contract version used to validate. |
| `sanitized_headers`, `metadata` | JSONB ! | JSON objects; credentials excluded. |

`raw.raw_records` is append-only for application roles. Duplicate acquisitions
remain separate rows; logical deduplication happens downstream.

### Run, checkpoint, work, and webhook tables

| Table / grain | Columns (type; `?` nullable) | Keys and checks |
| --- | --- | --- |
| `ops.pipeline_runs` — one bounded run | `run_id UUID`, `stage TEXT`, `source_system TEXT?`, `source_account_id TEXT?`, `stream_name TEXT?`, `batch_id UUID?`, `requested_window_start TIMESTAMPTZ?`, `requested_window_end TIMESTAMPTZ?`, `airflow_dag_id TEXT?`, `airflow_run_id TEXT?`, `started_at TIMESTAMPTZ`, `finished_at TIMESTAMPTZ?`, `status TEXT`, `error_code TEXT?`, `error_message TEXT?`, `log_reference TEXT?` | PK `run_id`; stage is ACQUIRE/TRANSFORM/PUBLISH/RECOVER; status is RUNNING/SUCCEEDED/FAILED/CANCELED; only RUNNING has null finish; valid interval/time order; deferred batch FK resolves run/batch creation order. |
| `ops.task_attempts` — one task execution attempt | `attempt_id UUID`, `run_id UUID`, `task_name TEXT`, `attempt_number INTEGER`, `started_at TIMESTAMPTZ`, `finished_at TIMESTAMPTZ?`, `status TEXT`, `error_code TEXT?`, `error_message TEXT?`, `log_reference TEXT?` | PK `attempt_id`; FK run; UQ `(run_id, task_name, attempt_number)`; positive attempt; status RUNNING/SUCCEEDED/FAILED/RETRYABLE. |
| `ops.extraction_checkpoints` — one source/account/stream | `source_system TEXT`, `source_account_id TEXT`, `stream_name TEXT`, `completed_window_end TIMESTAMPTZ`, `successful_run_id UUID`, `updated_at TIMESTAMPTZ` | Composite PK; successful run FK. Written only after all required raw/work is durable. |
| `ops.processing_work` — one recoverable job | `work_id UUID`, `dedupe_key TEXT`, `work_type TEXT`, source/account, `source_entity_id TEXT?`, `trigger_raw_record_id UUID?`, `inbox_id UUID?`, `state TEXT`, `cycle_attempts INTEGER`, `next_attempt_at TIMESTAMPTZ?`, `lease_until TIMESTAMPTZ?`, error fields, created/updated times | PK; UQ dedupe key; raw/inbox FKs; state PENDING/LEASED/SUCCEEDED/FAILED/DEAD_LETTER; attempts 0–5; only LEASED has a lease deadline. |
| `ops.webhook_inbox` — one logical message | `inbox_id UUID`, source/subscription/webhook IDs, `event_type TEXT`, `source_account_id TEXT`, `resource_url TEXT`, `first_raw_record_id UUID`, `first_received_at TIMESTAMPTZ`, `fetch_state TEXT` | PK; UQ `(source_system, subscription_id, webhook_id)`; raw FK; fetch state PENDING/LEASED/SUCCEEDED/FAILED/IGNORED. |
| `ops.webhook_delivery_attempts` — every delivery | `delivery_id UUID`, source, `subscription_id TEXT?`, `webhook_id TEXT?`, `inbox_id UUID?`, `raw_record_id UUID?`, `received_at TIMESTAMPTZ`, `signature_valid BOOLEAN`, `freshness_valid BOOLEAN`, `accepted BOOLEAN`, `response_status INTEGER`, `rejection_reason TEXT?` | PK; inbox/raw FKs; response 100–599; accepted delivery requires both validations and durable raw plus inbox references. Rejections are still auditable. |

### Batch, release, and exception tables

| Table / grain | Columns (type; `?` nullable) | Keys and checks |
| --- | --- | --- |
| `ops.transform_batches` — one immutable manifest | `batch_id UUID`, `run_id UUID`, `mapping_version TEXT`, `transformation_version TEXT`, `manifest_frozen_at TIMESTAMPTZ`, `status TEXT`, `test_artifact_reference TEXT?`, `published_at TIMESTAMPTZ?` | PK; run FK/UQ; status FROZEN/BUILDING/TESTED/PUBLISHED/FAILED; only PUBLISHED has publish time. |
| `ops.batch_inputs` — one raw member | `batch_id UUID`, `raw_record_id UUID` | Composite PK and FKs. Explicit manifest avoids unsafe numeric-ID cutoffs. |
| `ops.publication_state` — active release per name | `publication_name TEXT`, `batch_id UUID`, `published_at TIMESTAMPTZ`, `transformation_version TEXT`, `mapping_version TEXT` | PK name; batch FK/UQ. |
| `ops.data_exceptions` — deduplicated issue | `exception_id UUID`, `exception_key TEXT`, `rule_id TEXT`, `severity TEXT`, `state TEXT`, source/account/entity IDs nullable, run/batch/raw IDs nullable, `processing_version TEXT`, `reason TEXT`, `details JSONB`, first/last seen, `resolved_at TIMESTAMPTZ?` | PK; UQ exception key; lineage FKs; object details; INFO/WARNING/ERROR/BLOCKING; OPEN/ACKNOWLEDGED/RESOLVED; resolution timestamp iff RESOLVED. |

## Configuration

M07 adds read-only live operational views, not business tables/columns. Exact
column types, nullable fields, grain, secret exclusions and grants were finalized
before migration 006 in [the M07 contract](08_M07_REPORTING.md#finalized-fields-and-constraints).
These expose live audit separately from publication-time `mart.source_health`.
M07 operations revision adds two restricted detail projections (observed order
history and recorded current eBay line allocations), with fields/grain finalized
before migration 007 in the same reporting contract. No base-table grants or
canonical business-state changes are needed.

`config.product_mapping` has: `mapping_id UUID ! PK`, `mapping_version TEXT !`,
source/account `TEXT !`, source listing/variant/SKU `TEXT ?`,
`canonical_variant_id TEXT !`, `mapping_status TEXT !`, `valid_from
TIMESTAMPTZ !`, `valid_to TIMESTAMPTZ ?`, and `created_at TIMESTAMPTZ !`.
At least one source identifier is present; valid-to is after valid-from. Active
CONFIRMED exact identifier tuples, listing/variant keys, and listing-only keys
are unique. Account-scoped SKU fallback
ambiguity is deliberately not hidden by a database uniqueness rule: dbt must
detect and publish it as an exception. The four `s01-v1` rows come only from
the approved independent mapping fixture.

## Published history/current fields

| Table / grain | Columns (type; `?` nullable) | Keys and checks |
| --- | --- | --- |
| `core.order_snapshot_history` — one distinct observed source version | `snapshot_id UUID`, source/account/order IDs, source created/updated and first-observed times, `content_fingerprint BYTEA`, three source status texts nullable, three common state texts, `currency TEXT`, five `NUMERIC(20,6)?` order amount components, mapping/transformation versions, `batch_id UUID` | PK snapshot; UQ scoped order + source update time + fingerprint; fingerprint 32 bytes; batch FK; time ordering. Mapping corrections do not create source versions. |
| `core.order_line_snapshot_history` — line in parent snapshot | `snapshot_id UUID`, `source_line_id TEXT`, listing/variant/SKU/title nullable, `canonical_variant_id TEXT?`, `mapping_status TEXT`, `quantity INTEGER`, unit/gross/discount/tax amounts nullable, `currency TEXT`, `fulfillment_evidence JSONB` | PK `(snapshot_id, source_line_id)`; parent FK; quantity >0; object evidence. Unmapped lines remain present. |
| `core.snapshot_evidence` — resource supporting snapshot | `snapshot_id UUID`, `raw_record_id UUID`, `evidence_role TEXT`, `resource_fingerprint BYTEA`, `resource_observed_at TIMESTAMPTZ` | PK all three identity columns; history/raw FKs; 32-byte resource fingerprint. Multiple resources may support one snapshot. |
| `core.orders_current` — latest justified scoped order | source/account/order IDs, `snapshot_id UUID`, source created/updated/observed times, three common states, `currency TEXT`, `items_gross_amount NUMERIC(20,6)?`, `source_order_total_amount NUMERIC(20,6)?`, `published_batch_id UUID` | Composite PK scoped order; snapshot FK/UQ; batch FK. Older/equal-time conflicting evidence cannot silently replace it. |
| `core.order_lines_current` — latest line in current order | scoped order + `source_line_id TEXT`, snapshot, nullable listing/variant/SKU/title/canonical variant, mapping status, positive quantity, nullable unit/line gross, currency, batch | Composite PK scoped line; scoped order FK; snapshot/batch FKs. |

## Published marts and report views

| Table / grain | Fields and constraints |
| --- | --- |
| `mart.order_activity_daily` — UTC creation date × source/account × currency | Grain columns form PK; nonnegative `order_count BIGINT`; nullable source-order total `NUMERIC(20,6)`; required batch FK. Cancellation does not erase original activity. |
| `mart.product_activity_daily` — date × source/account × product bucket × mapping state × currency | Required `product_bucket_key` equals canonical variant or `__UNMAPPED__`; nullable `canonical_variant_id`; nonnegative line/unit counts; nullable merchandise amount; required batch FK. |
| `mart.order_status_current` — source/account × three states | Grain columns form PK; nonnegative order count; required batch FK. |
| `mart.source_health` — source/account/stream | Nullable completed window/acquisition/publication/batch, nonnegative pending/failed/blocking counts, coverage COMPLETE/INCOMPLETE/UNKNOWN/UNAVAILABLE. A recent timestamp alone cannot imply COMPLETE. |

The read-only role sees only stable views in `report`: `publication_state`,
`orders_current`, `order_lines_current`, `order_activity_daily`,
`product_activity_daily`, `order_status_current`, and `source_health`. It has no
raw, operational-table, configuration, build-schema, or source-database access.

M05B's finalized extension above binds clock/validation mode and fixed polling
windows to durable execution/batch provenance (migration 004). M07 still needs
secret-free live failure/work/test views for the report role; these views are not
implemented. Finalize their precise definitions, constraints and permissions here
before dependent DDL. Do not grant report users
direct access to ops/raw or reuse the stable source_health timestamp as live status.

## Ownership and evidence links

### M08D reuse and nonblocking coordination (2026-11-12; before migrations010/011)

`cache.etsy_payloads`: derived, logged, append-only canonical payload cache.
PK `(source_system TEXT, source_account_id TEXT, byte_sha256 BYTEA,
normalization_version TEXT)`; all NOT NULL. Source must be etsy_sim, account
nonempty, byte hash32bytes, version32lowercase hex (code-version identifier, NOT
source fingerprint). `source_payload JSONB NOT NULL`, `order_json JSONB NOT NULL`,
`content_fingerprint BYTEA NOT NULL CHECK(length=32)`,
`cached_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()`.
Version is local_md5 of the three canonical function definitions. Mapping version
does not change source identity. Reuse requires matching scope/hash/version AND
identical parsed JSONB text (including numeric scale); mismatch fails the dbt
transaction, never overwrites. JSONB equality alone would equate1 and1.0.
No raw FK because one cache row may serve many acquisitions. Staging joins back
to every eligible raw in the frozen manifest, preserving lineage/time/duplicates.
Owner platform_owner; platform_transform USAGE cache,SELECT/INSERT only. No
ingest/publisher/report/PUBLIC access. Cache is rebuildable derived state, not
business truth; full manifest, all business tests and atomic publish stay required.

`ops.source_cycle_owners`: PK `(source_system TEXT,source_account_id TEXT)`;
source internal_web/ebay_sim/etsy_sim, nonempty account. `run_id UUID NOT NULL`
FK pipeline_runs, `acquired_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()`.
Pointer may be replaced only after the prior workflow is terminal SUCCEEDED or
FAILED; RUNNING owners are never auto-expired or stolen. Same-owner retry allowed.
Existing source advisory lock fences active processes; durable pointer preserves
source ordering while worker is rescheduled. Terminal Airflow owner with RUNNING
workflow requires existing explicit operator abort, not automatic state repair.

`ops.coordinator_waits`: PK `(run_id UUID,wait_kind TEXT,task_try_number INTEGER)`;
run FK pipeline_runs; kind source_slot/release_slot; task_try_number>0.
`measurement_id UUID NOT NULL UNIQUE` FK execution_measurements. Its existing
measurement started_at is the durable infrastructure-wait clock across pokes.
Deadline=started_at+configured wait_seconds; no reset on reschedule/restart.
Actual Airflow retry uses a new task_try_number, matching prior per-attempt wait
behavior; business five-attempt budgets remain untouched. No source leases/time
limits are increased. platform_ingest SELECT/INSERT/UPDATE owner pointers,
SELECT/INSERT waits; platform_transform SELECT both. PUBLIC/report no access.
New live-only reschedule path uses exit75 for coordinator contention, not failure;
legacy/manual CLI and S01 retain blocking coordination. Same task_id cycle and
four DAG identities remain. Scheduler queues waiting tasks without a worker;
DB guards still protect shared candidates and atomic publication.

M08D physical-plan experiment: `build.stg_website_observations` and
`build.int_website_versions` change from views to per-batch dbt tables. The
existing SELECTs define identical columns/types/nullability and identities; no
stable warehouse/source column or constraint changes. These are disposable build
relations rebuilt under the same global release barrier, not incremental source
state. Full model/test and atomic-publish gates remain unchanged. Verify compiled
SQL multiset parity before deploying; see19_M08D_MEASUREMENT.md and STATUS.

### M08D bounded Etsy reconciliation (finalized before migration 009)

No business/source fields change. `ops.etsy_recovery_scans` has grain one scan
of the immutable recovery window in an existing collection run:

| Column | Definition / constraints |
| --- | --- |
| `run_id UUID NOT NULL` | FK `ops.pipeline_runs`; part of primary key |
| `scan_number SMALLINT NOT NULL` | 1..5; other PK part; monotonically allocated under existing collection advisory lock |
| `status TEXT NOT NULL` | RUNNING, VALIDATED or INVALID; only RUNNING may transition to a terminal status |
| `started_at TIMESTAMPTZ NOT NULL` | Actual DB clock, immutable |
| `finished_at TIMESTAMPTZ NULL` | NULL iff RUNNING; otherwise >= started_at |
| `error_code TEXT NULL` | PAGE_SET_CHANGED iff INVALID, otherwise NULL |

At most one non-INVALID scan per collection. No delete, identity/time rewrite,
terminal-row update or retry-budget reset. Five scans is an additional ceiling,
NOT five fresh HTTP budgets. `ops.etsy_http_attempts.recovery_scan_number SMALLINT?`
references `(run_id,scan_number)` and is allowed only when `work_id IS NULL`.
Existing attempts remain unchanged/NULL; scan1 may adopt those legacy page audits.
For every URL, the total persisted HTTP attempts across ALL scans stays <=5;
attempt_number continues from the existing count, including legacy attempts.
Cache reuse is restricted to the current scan (plus legacy NULL for scan1).
Only a count/order-inconsistent scan becomes INVALID. Partial transport failures
resume the same scan and its successful pages; VALIDATED scans resume processing
without refetching. A new scan is never allocated after validation. HTTP-budget
exhaustion stops before any further request, never resets the budget or invalidates
a scan just to allocate another. Partial pages do not enqueue new receipt work;
validated pages enqueue with unchanged receipt-work identities. Checkpoint moves
only after all required receipt work succeeds. This is bounded reconciliation,
not a provider snapshot-isolation guarantee. `platform_ingest`: SELECT/INSERT/
UPDATE scans, SELECT/INSERT existing HTTP attempts; no new UPDATE attempt grant.
`platform_transform`: SELECT scans. Report users/PUBLIC have no table access.

M07 report/query and telemetry extension: finalized before migration 008 in
[09_M07_SCALE_MONITORING.md](09_M07_SCALE_MONITORING.md). Adds presentation review
projection, seek/lookup/history/time indexes, immutable real execution measurements,
sanitized latest scheduler observations and nullable actual work recording clock
(new inserts only). These do not redefine source snapshots or business states.
Report views only; no report base-table access or credentials are added.

M06 readiness: existing inbox/delivery/work tables are reusable foundations, not
a completed Etsy worker design. Before dependent DDL, finalize lease ownership/
fencing, bounded processing-cycle attempts, recovery identity/checkpoints and
receipt evidence links as required by [07_M06_READINESS.md](07_M06_READINESS.md).
This review adds no physical columns, grants or runtime state.

| Writer | Allowed responsibility |
| --- | --- |
| `website_writer` / `marketplace_writer` | Own/write only their simulator source database. Marketplace pipeline code receives no database role. |
| `website_reader` | Read-only website source role; source-table grants arrive with the M02 source schema. |
| `platform_ingest` | Append raw and maintain acquisition/run/work/webhook/exception state; cannot publish business tables. |
| `platform_transform` | Read raw/config/ops, maintain transform batch metadata, and create candidate relations in `build`; cannot write stable core/marts. |
| `platform_publisher` | Copy already-tested candidates into stable core/marts and update publication state. |
| `platform_report` | Select report views only. |
| `airflow_app` | Own the isolated `airflow_meta` database only. |

Field meaning derives from `docs/01_BUSINESS.md` A4–A5, source identity and
history rules in `docs/02_SOURCE_CONTRACTS.md` B3–B5, the approved CSV contracts
in `docs/contracts/`, and architecture sections C3.3–C3.5. Exact S01 fingerprint
behavior remains defined by `fixtures/s01/fixture_tools.py` and its tests; this
schema does not redefine it.

### M08D page reuse dictionary (finalized before migration014)

No source/business columns or fingerprints change. New acquisition references
identify actual JSON elements; never synthesize an HTTP response per element.

| Relation / grain | Columns and constraints |
| --- | --- |
| ops.collection_options: one opted-in collection | run_id UUID PK/FK pipeline_runs; settings JSONB object NOT NULL; immutable on retry, includes non-null mode='page-reuse', workers1..2 and page size1..200. The validation predicate must be TRUE, not SQL UNKNOWN; JSON null is invalid. |
| ops.ebay_collection_scans: one bounded discovery scan | run_id UUID FK, scan_number SMALLINT1..5 composite PK; status RUNNING/VALIDATED/INVALID; started_at actual TIMESTAMPTZ; finished_at nullable iff RUNNING. HTTP budgets span scans; only RUNNING can finish. |
| ops.ebay_scan_restarts: one enrichment conflict after a validated scan | (run_id,scan_number) PK/FK ebay_collection_scans; recorded_at TIMESTAMPTZ actual; immutable append-only marker, permits the next bounded discovery scan without rewriting terminal scan audit. |
| ops.acquisition_elements: one accepted entity in an actual page | raw_record_id UUID FK, source_entity_id TEXT nonempty composite PK; element_index INTEGER>=0, UNIQUE(raw_record_id,element_index); collection_run_id UUID FK, scan_number SMALLINT1..5; recorded_at actual TIMESTAMPTZ. Immutable. Trigger validates raw source/account/status, page index/identity and a VALIDATED source-specific scan. Source/account derive from raw, not another copied payload. |
| cache.etsy_elements: one versioned receipt computation | source_system TEXT='etsy_sim', source_account_id TEXT nonempty, source_entity_id TEXT nonempty, element_sha256 BYTEA32, normalization_version TEXT MD5 composite PK; source_payload/order_json JSONB objects, content_fingerprint BYTEA32, cached_at TIMESTAMPTZ actual. Hash derives from JSONB element text, not parent page bytes; raw/evidence still retains whole-response byte hash. Immutable. |

Ingest may SELECT/INSERT options/elements, SELECT/INSERT/UPDATE scan state; no
UPDATE/DELETE accepted elements/options. Transform may SELECT these and
SELECT/INSERT derived element cache; publisher reads references only as needed.
PUBLIC/report receive no new access. New mode remains disabled until migration,
new compiled/full-dbt qualification and explicit release/bootstrap are approved.
Cooldown lookup indexes: raw(source_system,source_account_id,metadata fetched_at)
restricted to429/503, plus Etsy HTTP attempts(raw_record_id,recorded_at). These
support actual shared-cooldown predicates, not speculative business-model indexes.
