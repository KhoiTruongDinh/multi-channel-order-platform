# Target field dictionary and storage contract

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
