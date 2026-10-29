# B. Source contracts and S01 acceptance

## B1. Intended sources and API discovery

The agreed topology is a simulated internal website database, an eBay-style polling API, and an Etsy-style webhook plus receipt API, all running locally. eBay and Etsy are the selected public-contract references. Shopee and Tiki were examples, not selected sources.

Study actual public integration documentation before designing source adapters or simulators. The required external contract is the API/export/event structure provided to partners, not the marketplace’s private internal database schema.

- Check order and item identifiers, product/variant IDs, seller scope, field types, currency, amount components, timestamps, timezone, and status semantics.

- Check filters by creation/update time, pagination, ordering guarantees, quotas, lookback windows, and available backfill methods.

- Check events/webhooks/history versus current-state endpoints; verify whether order-level and item-level states differ.

- Check authentication, seller authorization, development access, and whether a usable sandbox exists.

- Record what is supported, unavailable, or unverified. Do not promise a sync frequency or complete history before this assessment.

Local simulation is the primary environment by explicit user choice. Seller accounts, app registration, production access, and provider sandbox onboarding are outside the initial scope. Provider sandboxes or test facilities are optional later checks; they are not prerequisites. This project does not claim a completed integration with live marketplaces.

## B2. Agreed local simulation approach

Use a small, deterministic business simulator rather than building three complete commerce applications. One generator can create a shared internal catalog, channel-specific listings, distinct orders on each channel, order lines, and valid lifecycle changes. Use a fixed seed and a configurable simulated clock.

The same product sold on three channels represents separate orders, not three copies of one sale. Generate consistent quantities and amount components under documented rules. Test assumptions such as cancellation rates are configuration choices, not measured marketplace behavior.

Serve the website data through a relational database and marketplace data through distinct API contracts informed by verified documentation. A single local API service may host both marketplace simulators. The ingestion pipeline must use those interfaces rather than reading their backing storage directly.

Keep an independent scenario ledger for expected results. Test code may use it to verify the platform, but the production pipeline must not read the expected-answer ledger. Separate deliberate fault injections from normal events and preserve their provenance.

The environment is simulated and inspired by selected public eBay/Etsy contracts;
it is not a certified replica. Approved detailed fields/rules are in workbook
tabs 13–18. Fixed website playback, the eBay HTTP subset and the M06 Etsy
webhook/receipt/recovery subset are implemented; see STATUS for runtime evidence.
An opt-in current-clock source generator remains M08 work.
Scheduling does not advance frozen fixture state. The operational clock/mode
plan in [06_AUTOMATION.md](06_AUTOMATION.md) does not change S01 or these contracts.

## B3. Engineering behavior and acceptance scenarios

- Repeated page or batch: processing the same source version again does not duplicate orders, lines, or history entries.

- Old order updated today: incremental extraction captures the change even though the creation date is outside today’s window.

- Out-of-order updates: an older update cannot silently overwrite newer state; ordering/version rules must follow the source contract, with conflicts exposed.

- Missing mapping or unfamiliar status: preserve the source record and publish an exception without inventing a match.

- API error or quota limit: retry and resume from a justified checkpoint without silently skipping pages or windows.

- Source outage or uncertain coverage: mark the source/report accordingly rather than claiming complete data.

- Backfill and reprocessing: rebuilding a defined interval yields the expected state on the same source versions, without duplicate records.

- History limitation: distinguish event time from observed time and state explicitly when intermediate changes cannot be recovered.

Reconciliation compares compatible scopes and definitions. Count order headers against order headers, lines against lines, and like-for-like monetary components. Do not expect three different channels to have matching totals. Actual reconciliation rules will be derived from the selected contracts and agreed business definitions.

## B4. Business setting and internal website source

Working business assumption: a retailer sells physical products with variants through its own website and both marketplaces. A handmade ceramic mug with color and capacity variants is a useful example. This is a project assumption, not a platform requirement.

The website is an independent transactional source, not the unified warehouse model. It supports multi-line orders, quantities above one, payment attempts, multiple shipments, and partial shipping. Initial website cancellation requests apply to the whole order.

| Source table / grain | Main columns |
| --- | --- |
| customers — one website customer | customer_id (PK), display_name, email, created_at, updated_at |
| products — one product family | product_id (PK), product_name, category, is_active, created_at, updated_at |
| product_variants — one sellable variant | variant_id (PK), product_id (FK), sku, attributes, current_price, currency, is_active, updated_at |
| orders — one website order | order_id (PK), order_number, customer_id (FK), created_at, updated_at, currency, payment_status, fulfillment_status, cancellation_status, items_gross_amount, discount_amount, shipping_amount, tax_amount, order_total_amount |
| order_items — one line within an order | order_item_id (PK), order_id (FK), variant_id (FK), sku_at_purchase, title_at_purchase, quantity, unit_price, line_discount_amount, line_tax_amount, created_at, updated_at |
| payment_transactions — one payment attempt or transaction | payment_transaction_id (PK), order_id (FK), transaction_type, status, amount, currency, provider_reference, occurred_at, updated_at |
| shipments — one parcel | shipment_id (PK), order_id (FK), carrier, tracking_number, status, shipped_at, delivered_at, updated_at |
| shipment_items — a line quantity in a parcel | shipment_id (FK), order_item_id (FK), quantity; composite PK (shipment_id, order_item_id) |
| cancellation_requests — one whole-order cancellation request | cancellation_id (PK), order_id (FK), reason_code, status, requested_at, resolved_at, updated_at |

## Website integrity rules

Order items preserve purchase-time title, SKU, and price; later catalog changes must not rewrite past purchases. Child changes that affect the order snapshot update orders.updated_at within the same transaction. Incremental extraction must obtain a consistent order snapshot, rather than reading unrelated child versions.

Use exact decimal arithmetic for amounts and timezone-aware timestamps. Shipment allocations must refer to lines from the same order; quantities allocated or shipped cannot exceed the allowed ordered quantity. Successful payments, failed attempts, and refunds must remain distinguishable. Exact enums, constraints, deletion semantics, and atomic extraction behavior belong in the source contract.

## B5. Selected marketplace field subsets

Overview only. The approved detailed subsets, requiredness, conditional fields and validation rules are maintained in workbook tabs 15–18; those definitions take precedence over this summary. Account context remains separate from payload fields.

| eBay Fulfillment API group | Selected fields / structure |
| --- | --- |
| Order identity | orderId, sellerId |
| Time | creationDate, lastModifiedDate — ISO 8601 UTC |
| Buyer | Selected available fields inside buyer; availability is contract-dependent |
| State | orderPaymentStatus, orderFulfillmentStatus, cancelStatus.cancelState |
| Order money | pricingSummary, including priceSubtotal, priceDiscount, deliveryCost, tax, total where returned |
| Payment / refund evidence | paymentSummary; selected payment and refund fields |
| Lines | lineItems[] |
| Line identity / product | lineItemId, legacyItemId, legacyVariationId when applicable, sku, title |
| Line quantity / money | quantity, lineItemCost, discountedLineItemCost when a promotion applies, total |
| Line fulfillment | lineItemFulfillmentStatus, lineItemFulfillmentInstructions |
| Shipping details | fulfillmentHrefs and the shipping fulfillment resource, including line allocations and tracking where supported |
| List envelope / retrieval | orders[], pagination metadata; lastmodifieddate filter, limit, offset |
| Endpoint distinction | getOrders returns cancelStatus.cancelRequests as an empty array; use getOrder to obtain populated cancellation request details. |

eBay lineItemCost is the whole line selling amount before discounts: unit price multiplied by quantity. Do not multiply it by quantity again. FULFILLED means considered shipped, not delivered to the buyer. Preserve IN_PROGRESS until a documented rollup rule and sufficient line/shipment evidence justify a more specific common state.

| Etsy Open API v3 group | Selected fields / structure |
| --- | --- |
| Order / account identity | receipt_id, seller_user_id, buyer_user_id; shop_id from request or webhook context |
| Time | created_timestamp, updated_timestamp — epoch seconds; the specification also exposes create_timestamp and update_timestamp aliases |
| State | status, is_paid, is_shipped |
| Order money | total_price, subtotal, grandtotal, discount_amt, total_shipping_cost, total_tax_cost, total_vat_cost, gift_wrap_price |
| Money representation | Money objects: amount, divisor, currency_code |
| Payment / refund evidence | payment_method, refunds[] |
| Lines | transactions[] |
| Line identity / product | transaction_id, listing_id, product_id, sku, title, variations |
| Line quantity / money | quantity, price, shipping_cost |
| Line timing | paid_timestamp, shipped_timestamp, expected_ship_date where available |
| Shipping | shipments[] |
| List retrieval | min_last_modified, max_last_modified, limit, offset; selected sorting parameters |
| Order webhook body | event_type, resource_url, shop_id |
| Webhook headers | webhook-id, webhook-timestamp, webhook-signature |

For Etsy money, normalize amount / divisor with exact decimal arithmetic; do not assume divisor is always 100. Order events selected for simulation are order.paid, order.canceled, order.shipped, and order.delivered. Event meaning must follow documentation: a cancellation notification is not by itself proof of a completed cancellation.

Keep webhook messages separate from receipt snapshots. A notification contains a resource reference, not the full order. Fetching the receipt later may return state newer than the notification. Use webhook-id for inbox deduplication, preserve timestamp/signature headers, and validate the original raw body. Polling by modification time is an additional recovery/reconciliation path, not a guarantee that every intermediate event can be recovered.

## B6. Common output and field mapping baseline

Publish orders_current at one row per source/account/order and order_lines_current at one row per source/account/order/line. Key components are source_system + source_account_id + source_order_id, adding source_line_id for a line. Preserve identifiers as strings in the common layer. SKU identifies a product reference, not an order-line transaction.

| Common field | Website | eBay | Etsy |
| --- | --- | --- | --- |
| source_system | Pipeline: internal_web | Pipeline: ebay_sim | Pipeline: etsy_sim |
| source_account_id | Configured store ID | Authenticated seller context | shop_id context |
| source_order_id | orders.order_id | orderId | receipt_id |
| source_line_id | order_item_id | lineItemId | transaction_id |
| source_created_at | orders.created_at | creationDate | created_timestamp |
| source_updated_at | orders.updated_at | lastModifiedDate | updated_timestamp |
| source_sku | sku_at_purchase | sku | sku |
| source_listing_id | Not applicable | legacyItemId | listing_id |
| source_variant_id | variant_id | legacyVariationId if present | product_id if present |
| product_title | title_at_purchase | title | title |
| quantity | quantity | quantity | quantity |
| line_gross_amount | quantity × unit_price | lineItemCost.value | quantity × price.amount / price.divisor |
| source_order_total_amount | order_total_amount | pricingSummary.total.value | grandtotal.amount / grandtotal.divisor |
| currency | Order/line currency | Amount.currency | Money.currency_code |
| payment / fulfillment / cancellation state | Explicit source state mapping | Source enums and relevant evidence | status, flags, and relevant evidence |
| canonical_variant_id | Catalog mapping | Listing/variation/SKU mapping | Listing/product/SKU mapping |
| ingested_at / raw_record_id / run_id | Pipeline-generated | Pipeline-generated | Pipeline-generated |

## Mapping and normalization rules

Map marketplace listings/variants to an internal sellable variant using explicit source/account-scoped identifiers. Treat SKU as optional and account-scoped. Avoid joining only on titles or assuming a listing always represents one variant. Unknown products remain in the data with an unresolved mapping and an exception.

Do not infer a line discount or allocate order-level shipping, tax, or discount without an explicit rule. Keep order amounts at order grain; joining them onto multiple lines must not multiply totals. Preserve source-reported totals and money components before deriving comparable metrics. Do not sum different currencies or label source order value as net revenue.

Unknown and unavailable values remain distinguishable from false and zero. Keep raw source statuses alongside common states. Pending cancellation, completed cancellation, payment, and refund evidence must not collapse into one status. Unknown enums or contradictory evidence generate exceptions.

Observed history stores what was actually seen, with source update time and observation time. Equal timestamps with different payloads need a conflict rule; a timestamp alone is not necessarily a complete source version. A later-arriving old snapshot must not overwrite newer state. Do not construct missing historical states from simulator ground truth.

Additional outputs include raw responses, mapping, observed snapshots, webhook inbox/delivery audit, exceptions and acquisition/processing audit. Their proposed storage and ownership are defined together in Section C3.

## B7. Official reference links

eBay Fulfillment API OpenAPI specification: https://developer.ebay.com/api-docs/master/sell/fulfillment/openapi/3/sell_fulfillment_v1_oas3.json

eBay order discovery and fulfillment semantics: https://developer.ebay.com/api-docs/sell/static/orders/discovering-unfulfilled-orders.html

Etsy Open API v3 specification: https://www.etsy.com/openapi/generated/oas/3.0.0.json

Etsy API reference: https://developers.etsy.com/documentation/reference/

Etsy webhooks: https://developer.etsy.com/documentation/essentials/webhooks/

Reference assessment date: 17 October 2026. Selected contract fidelity is a design target. No authenticated provider calls or sandbox integration have been tested. Recheck provider documentation when freezing the executable source contracts.

## B8. S01 — approved business scenario

Approved by the user on 18 October 2026. Business semantics and source contract v0.1 in B9 are agreed. The S01 orders, timeline and totals below are the sole acceptance baseline.

### B8.1 Catalog, orders, and assumptions

Simulation date: 17 October 2026. All scenario times are UTC. The clock may advance without waiting in real time. Physical ceramic mugs, blue variant V001 priced at USD 20.00 and white variant V002 priced at USD 22.00. Account scope: website store WEB01, eBay seller seller_sim_01, Etsy shop 7001. All product mappings exist; discount, shipping charge, and tax are zero for this scenario.

| Source / order | Lines and amount |
| --- | --- |
| Website / W1001 | WI1001: V001 blue × 2 at USD 20.00; total USD 40.00. SKU MUG-BLUE-350. |
| eBay / 12-10001-10001 | 10001001: V001 blue × 2, lineItemCost USD 40.00, SKU EB-BLUE-350. 10001002: V002 white × 1, lineItemCost USD 22.00, SKU EB-WHITE-350. Total USD 62.00. |
| Etsy / 9001001 | 8001001: V002 white × 1 at USD 22.00; total USD 22.00. SKU ET-WHITE-350. |
| Expected initial activity totals | 3 independent orders; 4 order lines; 6 ordered units; USD 124.00 merchandise value. A later cancellation does not delete the original order or purchase quantities. |

### B8.2 Source changes and observations

| UTC time | Source action | Pipeline observation |
| --- | --- | --- |
| 09:00 | Website creates unpaid W1001. | No read. |
| 09:01 | Website records successful payment. | No read. |
| 09:02 | eBay creates paid order; fulfillment not started. | No read. |
| 09:03 | No new business action. | Read website and eBay current snapshots. |
| 09:04 | Etsy paid receipt; emits order.paid. | Notification delivery intentionally delayed. |
| 09:05 | Etsy marks shipment; emits order.shipped. | No receipt read yet. |
| 09:06 | Deliver delayed paid notification. | Persist inbox; fetch receipt now paid and shipped, updated at 09:05. |
| 09:07 | Deliver shipped notification. | Fetch the same receipt version; do not add duplicate snapshot history. |
| 09:08 | Redeliver paid notification with same webhook-id. | Deduplicate logical inbox message; retain delivery-attempt audit. |
| 09:10 | Website cancellation request becomes pending. | No read. |
| 09:11 | No new business action. | Read website: cancellation requested, not completed. |
| 09:12 | eBay ships the entire blue line in one parcel; white line not shipped. | No read. |
| 09:13 | No new business action. | Poll eBay; fetch shipping fulfillment evidence for the shipped blue line. |
| 09:14 | Website approves whole-order cancellation; no completed refund. | No read. |
| 09:15 | No new business action. | Read website: canceled; previous successful payment remains. |

### B8.3 Expected current-state and history results

| Observation / order | Payment | Fulfillment | Cancellation |
| --- | --- | --- | --- |
| 09:03 / website | PAID | NOT_STARTED | NOT_REQUESTED |
| 09:03 / eBay | PAID | NOT_STARTED | NOT_REQUESTED |
| 09:06 / Etsy | PAID | SHIPPED | UNKNOWN |
| 09:07–09:08 / Etsy | Unchanged | Unchanged | Unchanged |
| 09:11 / website | PAID | NOT_STARTED | REQUESTED |
| 09:13 / eBay | PAID | PARTIALLY_SHIPPED | NOT_REQUESTED |
| 09:15 / website | PAID | NOT_STARTED | CANCELED |

Common status names are project vocabulary, not identical provider enums. eBay IN_PROGRESS alone is insufficient evidence for PARTIALLY_SHIPPED; use line and shipping fulfillment details. S01 does not assert DELIVERED for any order. Etsy cancellation remains UNKNOWN under the currently selected evidence rule; preserve the receipt's original status when returned, and review its full interpretation in the contract.

| Output / assertion after 09:15 | Expected result |
| --- | --- |
| Current orders / lines | 3 current orders; 4 current lines; 6 ordered units; USD 124.00 original merchandise value. |
| Website cancellation | 1 confirmed canceled order with USD 40.00 original merchandise value. Do not claim a completed refund. |
| Observed snapshot history | 6 versions: website 3 (paid, cancellation requested, canceled); eBay 2 (not started, partially shipped); Etsy 1 (first observed paid and shipped). |
| Webhook logical inbox | 2 unique messages: paid and shipped; paid is delivered twice, so 3 delivery attempts are audited. |
| Data-quality exceptions | None for valid S01. UNKNOWN is an explicit evidence limitation, not by itself an invalid record. |
| History count qualification | The six-version assertion assumes exactly the scheduled reads and payload versions above. Raw-response and delivery audit counts are separate; changing the read schedule can change observed history. |

### B8.4 Approved history principle

A receipt fetched after a delayed webhook still supplies current order and transaction details, so it can create an order and its lines even if the pipeline missed creation. A source creation timestamp can establish when an order was created without providing a snapshot from that time.

Record received payloads and acquisition attempts in raw/audit storage, deduplicate repeated logical versions in snapshot history, and keep the newest justified state in current tables. Preserve event notifications separately. Do not fabricate a past snapshot, such as changing is_shipped to false on a later receipt to invent an earlier unpaid/unshipped version. Reconstruction is only justified if actual source evidence supports it.

### B8.5 Recovery variants

Replay the same page or webhook; deliver an older eBay snapshot after the newer one; stop the worker after durable inbox storage; inject API 429/500/timeouts; and remove one product mapping in a separate test variant. Assert no duplicate current rows/history, no state regression, recoverable work, no prematurely completed extraction window, and a preserved unmapped line plus exception. Keep these variants separate from the valid S01 baseline.

## B9. Source contract v0.1 — approved baseline

Approved source-interface and recovery baseline. Detailed source schemas/rules are in workbook tabs 13–18 and dated repository exports. Fixed-fixture implementation progress is in D4; STATUS records the bounded M05/M06 runtime evidence and remaining limits. This section defines source behavior; physical design belongs in C3.

### B9.1. Interfaces and boundaries

| Interface | Agreed behavior / request |
| --- | --- |
| Website relational extraction | Read changed orders plus related order_items, payment_transactions, cancellation_requests, shipments, and shipment_items from one consistent source read. Every relevant child write also advances orders.updated_at atomically. Pipeline has read-only access. |
| eBay list | GET /sell/fulfillment/v1/order with filter=lastmodifieddate:[from..to], limit and offset. Retain the orders[] envelope and provider-style pagination fields. For S01 use limit=1 to exercise paging in later multi-order tests. |
| eBay details | GET /sell/fulfillment/v1/order/{orderId}; GET /sell/fulfillment/v1/order/{orderId}/shipping_fulfillment. The list response alone is not authoritative for populated cancellation requests. S01 partial-shipping normalization requires parcel date and line allocation evidence. |
| Etsy notifications | Source POSTs to a pipeline-owned callback such as /webhooks/etsy. The body has event_type, resource_url, shop_id; delivery metadata/signature are headers. Callback path is a project choice. |
| Etsy receipt | GET /v3/application/shops/{shop_id}/receipts/{receipt_id}. Receipt includes transactions[]; keep product/listing IDs when present and the source Money representation. |
| Etsy recovery list | GET /v3/application/shops/{shop_id}/receipts with min_last_modified, max_last_modified, limit, offset, sort_on=updated and sort_order=asc. Process results[]; initial scan and recovery do not depend on receiving every webhook. |
| Simulator control | Advance clock, reset fixtures, and inject faults through a test-only control interface, kept outside marketplace data contracts. Production ingestion cannot read simulator storage or the expected-answer ledger. |

Example eBay request (decoded for readability): GET /sell/fulfillment/v1/order?filter=lastmodifieddate:[2026-10-17T09:00:00.000Z..2026-10-17T09:03:00.000Z]&limit=1&offset=0. URL-encode filter punctuation when sending. Do not combine creationdate with lastmodifieddate for incremental extraction.

Example Etsy recovery request: GET /v3/application/shops/7001/receipts?min_last_modified=1792227600&max_last_modified=1792227960&limit=1&offset=0&sort_on=updated&sort_order=asc. These bounds represent 09:00–09:06 UTC on the fixture date.

### B9.2. Core validation and normalization

| Field / condition | Agreed rule |
| --- | --- |
| Identity | Require account context and an order ID; require line ID for each accepted line. Raw Etsy IDs remain integers as documented; common IDs are strings. Missing identity is quarantined, not guessed. |
| Source time | Website uses timezone-aware timestamps; eBay ISO 8601 UTC strings; Etsy epoch seconds. Normalize to UTC while preserving originals. Missing/invalid ordering time creates an exception and blocks blind replacement of current state. |
| Quantity / amounts | S01 quantities are positive integers; amounts use exact decimal arithmetic. eBay lineItemCost is already a line amount. Etsy price is converted by amount/divisor before multiplying quantity; divisor must be positive. S01 currencies are all USD. |
| Product reference | Keep all available listing, variant/product, and SKU identifiers. A nullable product reference does not erase the order/line. Missing canonical mapping produces a recoverable exception. |
| Missing vs null vs empty | Preserve distinctions. Missing optional values do not become zero/false. An empty collection is authoritative only when that endpoint's contract says it is complete; eBay list cancelRequests is a documented counterexample. |
| Source states | Retain original enums/flags. Only supported mappings produce common states; unknown values remain visible. For S01 use the state outputs in Section B8; broader enum coverage remains to be designed. |
| Raw provenance | Store source/account, endpoint or query, request/run ID, requested window, response status, fetched_at or received_at, raw payload reference and content hash. Keep callback headers and raw bytes for signature verification. |
| Snapshot identity | Compare source ordering time plus normalized content fingerprint within the entity scope; exclude ingestion metadata and normalize representation differences. Equal time with conflicting content is flagged rather than arbitrarily overwritten. Actual repeated state at a later source time may be a distinct observation. |
| Order + fulfillment enrichment | Track evidence timestamps/provenance independently. A later detail fetch is not automatically an atomic historical snapshot of the earlier order response. Re-fetch/reconcile inconsistent evidence before promoting a derived state; fixture data is paused during each scheduled read. |

### B9.3. Incremental reads, acknowledgments, and recovery

| Concern | Agreed project policy |
| --- | --- |
| Polling window | Capture an upper bound once per run; reread from committed upper bound minus a configurable overlap. Initial configurable overlap: 120 seconds. Boundaries may repeat records; deduplication is required. Overlap is not a guarantee against arbitrarily late source visibility. |
| Pagination | Finish all pages in the same requested time window. Fixed time bounds do not guarantee stable offsets on a changing provider dataset. Freeze the simulator clock for deterministic S01 reads; use mutable-page tests and reconciliation separately, without claiming provider snapshot isolation. |
| Acquisition checkpoint | Advance only after every required page/raw response is durably stored and parseable into identified work. Record pending entity/detail work before completing acquisition. A failed required page or malformed envelope leaves the window incomplete. |
| Processing checkpoint | Track materialization separately from acquisition. Retained raw data and pending work allow replay without refetching. Invalid entities remain quarantined with lineage; never report the processing stage as complete while required work is unresolved. |
| Webhook acceptance | Validate raw-body signature and allowed timestamp tolerance against the delivery clock, not the business simulation clock. Persist a unique inbox message and delivery audit before returning a success acknowledgment. Invalid signatures are rejected; persistence failure returns an error so the sender can retry. |
| Webhook worker | Fetch receipt from the configured simulator origin/path for the verified shop. Deduplicate inbox by source/subscription scope plus webhook-id. Two different event IDs can fetch the same receipt version, producing two inbox entries but only one history version. |
| Transient errors | Retry timeouts, 429 and selected 5xx with bounded exponential backoff and jitter; honor Retry-After when present. Initial configurable maximum: 5 total attempts (including the first attempt) per processing cycle, then leave work pending/failed for controlled replay. No silent skip. |
| Permanent or uncertain errors | 400: retain failed request and investigate; 401/403: stop affected source and flag configuration/access; 404 on a referenced receipt: retain pending work and reconcile, not an automatic deletion. Explicit provider-specific retry rules can refine this baseline. |
| Rebuild | Reprocess retained raw observations with a known mapping/contract version. Do not use the simulator truth ledger as ingestion input. Expose source coverage and unresolved work separately from the latest timestamp seen. |

### B9.4. Fixed fixture inventory

S01 fixture inventory: catalog/mapping seed; initial website records plus payment and cancellation transitions; eBay order snapshots at 09:02 and 09:12 plus one blue-line shipping fulfillment; Etsy receipt at 09:05 plus signed paid/shipped webhook deliveries; expected current orders, current lines, six observed history versions, two logical inbox messages, three delivery attempts, and zero baseline exceptions.

Numeric Etsy fixture timestamps: created/paid 09:04 = 1792227840; receipt updated/shipped 09:05 = 1792227900. Keep provider time fields in their documented representations; callback signature timestamps follow the chosen delivery execution clock. Local resource_url values use the simulator origin, never imply a live Etsy call.

Implementation checkpoint (2026-10-28): website acquisition/dbt/Airflow and the
M05A eBay fixed HTTP source/adapter are implemented; actual verification evidence
is in STATUS.md. The selected approved fields/rules remain unchanged. eBay source
controls are test-only and separate from its data listener; acquisition uses HTTP.
M06 now implements the local Etsy receipt/webhook subset; operating commands and
verification limits are in `orchestration/ETSY.md` and STATUS. Dated workbook exports do not update
automatically; no changed vendor/business semantics are implied by this checkpoint.
M05B website/eBay polling passed real scheduled-cycle, restart and bounded-retry
checks (STATUS). Separate checkpoint/validation modes preserve the original S01
sequence and source fields/rules. New current-clock source changes remain M08.


