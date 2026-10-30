# M07 reporting implementation contract

Current scale/monitoring revision: [09_M07_SCALE_MONITORING.md](09_M07_SCALE_MONITORING.md).
It supersedes unbounded snapshot loads/all-ID selectors while preserving the rules
and security below. Legacy small-fixture UI acceptance is not scale acceptance.

Selected 2026-10-29 after owner authorization: Streamlit, not a second BI tool.
M06 is committed as `dfd8d58a6f2b0c5a696a4ac830233f988bc6395a`.
Business definitions remain A5/S01; no source or transformation semantics change.

## Operations Manager revision (owner approved, 2026-10-29)

Primary audience: Operations Manager, English UI, read-only decision support.
Historical first revision default was **Order Operations** with a separate
**Data Quality & Pipeline** page. The current three-screen layout, bounded SQL,
filter semantics and monitoring in 09 supersede those UI/reader details. This earlier revision superseded the
original presentation-only two-page layout below, not its data/security contract.
Readiness review: existing published orders/lines/states suffice for review rules
and charts; two restricted detail projections below provide observed history and
recorded eBay shipment allocations. No new source fields, writable workflow,
canonical state mapping, dependencies or M08 continuous generator are required.

### Review rules (presentation labels, not new canonical business states)

| Rule | Exact condition on current published order | Suggested review, not an executable action |
| --- | --- | --- |
| Cancellation requested | cancellation_state=REQUESTED | Review cancellation in the source before further fulfillment |
| Partial fulfillment | cancellation_state=NOT_REQUESTED, payment_state=PAID, fulfillment_state=PARTIALLY_SHIPPED | Review recorded allocations and remaining items with fulfillment team |
| Fulfillment not started | cancellation_state=NOT_REQUESTED, payment_state=PAID, fulfillment_state=NOT_STARTED | Confirm payment/cancellation and fulfillment plan in source; not an instruction to ship |
| Payment pending | payment_state=UNPAID | Verify payment in source before proceeding; do not assume collection is due |
| Payment status verification | payment_state outside PAID/UNPAID, including null/UNKNOWN | Verify missing/unsupported payment information |
| Fulfillment status verification | fulfillment_state outside NOT_STARTED/PARTIALLY_SHIPPED/SHIPPED/DELIVERED | Verify missing/unsupported fulfillment information |
| Cancellation status verification | cancellation_state outside NOT_REQUESTED/REQUESTED/CANCELED AND fulfillment is NOT_STARTED/PARTIALLY_SHIPPED | Verify cancellation before deciding on fulfillment |

**Precedence:** CANCELED excludes every operational review rule, regardless of
payment or fulfillment. Canceled orders remain in All orders/Canceled and original
activity totals. REQUESTED suppresses both fulfillment-queue rules. Multiple other
reasons may coexist: one queue row per source/account/order with all reasons;
headline counts unique orders, reason counts may overlap. Sort oldest creation
first then composite key; this is not urgency or an SLA. Missing/ambiguous product
mapping is a separate Data issues bucket (including canceled orders), not a shipping
task. UNKNOWN cancellation alone on a shipped Etsy receipt is not an action item.

S01 acceptance: one operational review order, eBay, reason Partial fulfillment;
website CANCELED is excluded from operational review; Etsy SHIPPED/UNKNOWN is not
flagged. Cancellation requested=0, canceled=1, data mapping issues=0. Preserve
3 orders/4 lines/6 units/USD124 and original independent status values.

### Screen and chart contract

- Attention cards: Orders to review, Partial fulfillment, Cancellation requests,
  Canceled orders (counts of the whole date/source/account/currency cohort).
- Review-reasons bar chart counts unique orders per reason; no funnel/percentages
  suggesting disjoint reasons. Fulfillment-by-channel stacked bars exclude CANCELED
  and explicitly state that exclusion. Color/labels/tooltips are consistent.
- Needs review / All orders / Canceled / Data issues tables use human-readable
  English columns and state labels. Show why an order is listed and a suggested
  review. No UUIDs, raw payloads or pipeline logs on the default worklist.
- Source/account, UTC created-date and single-currency filters apply to the cohort
  and review charts. Review-reason selection filters only the worklist, not cards.
  Product filter affects only the separate original activity/product metrics.
- Detail selector uses the full composite order key. Show independent states,
  current items, review suggestions, observed version timeline and recorded line
  shipment allocations where available. No fabricated intermediate paid-only
  Etsy snapshot, parcel allocation, delivered date or refund. Empty allocation
  evidence is not proof that nothing shipped. Do not infer Etsy line allocations
  from order-level shipped state. Historical observations are not event completeness.
- Compact source availability summary uses last acquisition/publication/read times,
  flags failures newer than the last good publication without calling old injected
  failures current outages. Coverage remains UNKNOWN; audit IDs under an expander.
- No overdue/urgent ranking, shipping/cancel/refund buttons, write-back, owner
  assignment or remediation. No daily trend with only one observed creation date.

### Additional detail view fields (finalized before migration 007)

Owner-rights restricted views; report role SELECT only, PUBLIC none; no base access.

| View / grain | Explicit fields |
| --- | --- |
| `report.order_observed_history`, published observed snapshot | snapshot_id UUID!, source_system/account/order TEXT!, source_updated_at TIMESTAMPTZ!, first_observed_at TIMESTAMPTZ!, payment/fulfillment/cancellation_state TEXT!, currency TEXT!, source_order_total_amount NUMERIC(20,6) nullable |
| `report.line_shipment_allocations`, current eBay line x recorded fulfillment allocation | source_system/account/order/line TEXT!, fulfillment_id TEXT nullable, shipped_at TEXT nullable (retained source timestamp), allocated_quantity INTEGER nullable, carrier TEXT nullable; only matching lineItemId allocations; no tracking number or raw JSON |

These are safe projections of already dbt-normalized history/retained evidence;
they do not change warehouse states or derive a new shipment/delivery contract.
History/detail reads join the same report snapshot; no separate detail DB calls.
Additional acceptance: rules/precedence/multiple reasons, same order ID across
accounts, unknown states, chart totals, reason/product filter independence, order
selection/history/allocations, secret exclusions and no new report-role writes.

## Ordered process

1. Finalize baseline view columns before migration 006, detail fields before 007,
   and operational review rules before their dependent UI/tests.
2. Add restricted owner-rights views, explicit report grants and bootstrap/rerun.
3. Implement report-role-only snapshot reader, then UI and filters.
4. Test review precedence/charts/selection/history plus golden totals, grain,
   filters, nulls, snapshot isolation, role permissions,
   secret exclusion, newer failed run vs good publication, empty/unavailable DB,
   and UI interaction with Streamlit AppTest; run local HTTP health.
5. Record actual commands/limits in STATUS, leave M07 unstaged, stop before M08.

## Finalized fields and constraints

No new business tables or keys. Existing report business views remain unchanged.
New views are explicit projections, owned by the migration administrator; no
`security_invoker` or base-table grants to `platform_report`. Revoke PUBLIC;
report role gets SELECT only. No raw bytes/JSON, headers, URLs, paths, log refs,
exception reason/details, free-form error messages or secrets reach these views.

| View / grain | Final columns (nullable unless noted) |
| --- | --- |
| `report.live_source_health`, one approved source/account | source_system TEXT!, source_account_id TEXT!, publication_name TEXT!, last_successful_acquisition_at TIMESTAMPTZ, last_failed_at TIMESTAMPTZ, pending_work_count BIGINT!, failed_work_count BIGINT!, unresolved_exception_count BIGINT!, blocking_exception_count BIGINT!, coverage_state TEXT! fixed UNKNOWN |
| `report.live_runs`, one source-scoped pipeline run | run_id UUID!, source_system TEXT!, source_account_id TEXT!, stage TEXT!, stream_name TEXT, status TEXT!, requested_window_start/end TIMESTAMPTZ, started_at TIMESTAMPTZ!, finished_at TIMESTAMPTZ, batch_id UUID; no free-form error fields |
| `report.live_test_outcomes`, one source-scoped batch | batch_id UUID!, source_system TEXT!, source_account_id TEXT!, status TEXT!, validation_mode TEXT!, manifest_frozen_at TIMESTAMPTZ!, published_at TIMESTAMPTZ; test_outcome TEXT! = PASSED for TESTED/PUBLISHED, FAILED_OR_INTERRUPTED for FAILED, NOT_FINISHED otherwise (batch status is not a parsed dbt test result) |
| `report.live_exceptions`, one unresolved exception | exception_id UUID!, rule_id TEXT!, severity TEXT!, state TEXT!, source_system/account/entity TEXT nullable, run_id/batch_id/raw_record_id UUID nullable, first_seen_at/last_seen_at TIMESTAMPTZ!; no reason/details |
| `report.live_checkpoints`, one source/account/stream | source_system/account/stream TEXT!, completed_window_end TIMESTAMPTZ!, updated_at TIMESTAMPTZ!, successful_run_id UUID! |

Acquisition freshness excludes Etsy webhook ACK/inbox no-op runs, using completed
`receipt_work`, `receipts`, `receipts_polling` and test-scoped recovery scans;
website/eBay use their successful ACQUIRE runs. Empty completed API scans remain
valid acquisition, not new orders or complete coverage. Historical test evidence
is visible/labeled, not suppressed as a current outage. No SLA threshold is invented.

## Reporting and display

- Each render/Refresh opens one bounded read-only REPEATABLE READ transaction and
  reads publication mapping, current orders/lines and live health together. No
  query-result cache or background refresh. Widget changes also reread; browser
  data never claims to update merely because Airflow publishes.
- UTC source-created dates select an order cohort (inclusive dates). Source/account
  filter preserves composite identity. Select one currency; never sum currencies.
- Product filter affects only line count, quantity, merchandise and product totals.
  Order count/order totals remain explicitly labeled cohort-wide. Canceled orders
  stay in original activity; current state is not historical end-of-day state.
- Decimal money, separate source order total and line merchandise. Empty counts
  are zero; missing money is Unknown, never silently zero. Unmapped lines retain
  an UNMAPPED bucket. Payment/fulfillment/cancellation stay separate.
- Current layout: Multi-channel Overview, Order Operations and Pipeline Monitoring
  as defined in 09. The earlier two-page layout is superseded.
  Source publication IDs are in an audit expander, not the primary manager screen.
  Show read UTC time independently of source observation/update time.
- Local Compose `m07` profile, localhost:8501 default, `platform_report` password
  only. No writer/API/signing/Airflow credentials, simulator mounts or Docker socket.
  Connection failure is a sanitized unavailable message, not empty successful data.

API references: [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
and [execution model](https://docs.streamlit.io/develop/concepts/architecture/fragments).
Charts use the already pinned Altair package through
[st.altair_chart](https://docs.streamlit.io/develop/api-reference/charts/st.altair_chart).
Streamlit 1.66.1 (verified on PyPI) and Psycopg 3.3.6 use the fully resolved pinned
report-specific `requirements/m07.txt`, separate from dbt/Airflow.
