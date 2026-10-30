# A. Business requirements and outputs

## A1. Purpose and shared understanding

Build a reliable, unified order dataset from an internal sales website and external marketplaces whose structures, identifiers, statuses, and update mechanisms differ. The main deliverable is a reusable data product for downstream analytics and operations reporting.

The engineering problem is acquiring, interpreting, updating, and validating data across source boundaries. A daily-sales query alone is not the project. A small report will demonstrate that the integrated data is usable; a comprehensive dashboard is not the core scope.

## A2. Business request

Stakeholder role: Head of Operations at a business selling the same product catalog through its own website and multiple marketplaces.

“Each channel uses different product codes and order statuses. My team currently has to combine exports and interpret updates separately. I need a consistent view of orders and order items across channels, including their latest known status. I also need to know which sources are up to date and which records need investigation before the data can be trusted.”

A typical order may be created today, shipped later, and subsequently canceled or returned where the source supports those events. Repeated deliveries and delayed updates must not inflate counts or replace newer state with older information.

## A3. Users and responsibilities

- Data Engineering: source acquisition, normalization, incremental processing, deduplication, state/history handling, quality controls, lineage, recovery, and delivery of documented tables or views.

- DA/BI: downstream analysis, agreed KPI calculations, dashboards, and business interpretation using the published data.

- Head of Operations and operational teams: consumers of the resulting reports and exception information.

- Business owners and DE together: agree product mappings, status meanings, metric definitions, and data-availability expectations. DE must not invent business semantics.

## A4. Required data outputs

### A4.1. Unified orders and order lines

Provide a current-state order dataset and an order-line dataset. Preserve channel, seller/store, source order ID, source line identifier where available, source product/listing identifier, internal product mapping, quantity, supported monetary fields, original status, normalized status, source timestamps, and ingestion metadata.

Define each dataset’s grain and keys after inspecting the source contracts. An order number or product code alone is not assumed unique across channels or stores. Avoid joining order-level amounts to lines in a way that multiplies totals.

### A4.2. Product and status mappings

Maintain explicit relationships between channel-specific listings/variants and internal sellable products. Map source statuses to agreed common meanings while retaining the original value. Unmapped or ambiguous values must be visible rather than silently guessed. Decide whether mappings need effective dates during design.

### A4.3. Observed status history

Retain status changes the pipeline can actually observe, with source event/update time where available and observation/ingestion time. Complete business-event history is only possible if the source exposes the necessary events or history. Polling current state may miss intermediate transitions.

### A4.4. Source availability and processing audit

Expose the last successful synchronization, requested extraction window, successful processing checkpoint, errors, and known coverage limitations by source. Distinguish a successful request with no changes from an unavailable source. Do not claim complete coverage merely because the latest observed timestamp is recent.

### A4.5. Exception queue

Publish records requiring attention, such as unmapped products, unknown statuses, invalid required fields, conflicting updates, or failed processing. Include the reason, source identifiers, run context, and enough lineage for investigation and controlled reprocessing.

## A5. Reporting and dashboard contract — DRAFT

The report is a project deliverable. Here, report means the documented metrics and queries; dashboard means the screen that presents them. Business scope and S01 remain approved. The following reporting definitions and implementation choices are proposals for review.

### A5.1 Questions, metrics and S01 acceptance

Owner-approved M07 presentation revision: primary user is the Operations Manager,
English UI. **Order Operations** answers which orders need review and why,
with attention cards, fulfillment/reason charts, scoped worklist and observed order
detail. CANCELED excludes operational fulfillment review; REQUESTED routes to
cancellation review; UNKNOWN Etsy cancellation alone does not imply a task.
Missing mappings are data issues, not shipping instructions. Rules, limits and
acceptance are explicit in `08_M07_REPORTING.md`; no SLA, urgency, write-back or
new canonical states are introduced. Technical health is a separate page.

The approved scale/monitoring redo defaults to **Multi-channel Overview** to show
integrated published order volume, units and observed versions by channel. **Order
Operations** is a SQL-searchable, paginated workbench, not an all-order download.
**Pipeline Monitoring** uses actual execution time for attempts, duration, waits,
errors, backlog and scheduler observations. Source creation-date activity is not
new-order processing throughput. Current contracts/limits are in
`09_M07_SCALE_MONITORING.md`; historical S01 data is not a continuity/scale proof.

Operations page: filter by UTC source-created date, source/account and currency. Count distinct source/account/order keys from orders_current; count line keys and sum original ordered quantity from order_lines_current. Keep order amounts at order grain. Do not remove canceled orders from original order activity.

Proposed metrics for the complete S01 run: orders created 3; current lines 4; ordered units 6; original merchandise amount USD124; source-reported order amount USD124 under the S01 zero-discount/shipping/tax assumptions. Product units: V001 blue 4 and V002 white 2. The two monetary measures must remain separate outside these assumptions.

Current-state panel: website PAID / NOT_STARTED / CANCELED; eBay PAID / PARTIALLY_SHIPPED / NOT_REQUESTED; Etsy PAID / SHIPPED / UNKNOWN. Show the three dimensions separately. A creation-date filter selects an order cohort; status is the latest observed state of those orders, not their historical end-of-day state.

Data-health page: acquisition success/window by source, last successful publication, pending/failed work, blocking/unresolved exceptions and latest test outcome. Evidence counters may show six observed order versions, eight archived line rows, two logical webhook messages and three delivery attempts. These are audit counts, not additional sales.

Include a current-order detail table (one row per order), product totals including an unmapped bucket, and a source-health table. Keep unknown/unavailable values distinct from zero and false. A product filter affects line/product metrics; order-level monetary cards are not recomputed from filtered line joins. Either leave those cards explicitly unfiltered or provide a separately labeled selected-order cohort.

### A5.2 Data sufficiency and boundaries

Approved source fields and S01 evidence are sufficient for these outputs. Remaining preparation is technical: target column constraints, metric SQL, report access views and freshness behavior. Revenue recognition, margin, settlement, confirmed refunds and promised delivery/SLA analysis are outside the initial report. No new business discovery is required for S01.

Dashboard acceptance: figures match published SQL for the same batch/filter; S01 passes the values above; duplicate fetches/deliveries do not inflate figures; a failed build preserves prior published figures and displays failure/staleness context; an empty source window is distinguishable from an outage. Count and amount cards must not multiply through order-to-line joins.

### A5.3 Tool recommendation and synchronization

M07 technical resolution (2026-10-29, owner delegated routine choices): select Streamlit for the local dashboard, with source code/queries in reports/. Power BI remains an alternative, not a second deliverable. See 08_M07_REPORTING.md for finalized filter/access/refresh contracts; business/S01 definitions are unchanged.

The dashboard connects directly to PostgreSQL published mart/report views using a read-only role. It does not connect to the simulator, the fixture answers or an intermediate dbt build. Airflow runs ingestion → dbt/tests → successful publication; it need not push JSON or images into the dashboard.

On opening or pressing Refresh, the proposed Streamlit implementation reads publication_state and report datasets in one read-only REPEATABLE READ transaction, then renders that consistent result. Begin without query-result caching for S01. If caching is introduced later, include published_batch_id in the cache key and define expiration/invalidation. Database publication does not by itself refresh an already displayed browser page.

Every business page shows the publication ID/time for each included source.
Current releases are source-specific, so the consistent report label is a
source-to-batch mapping read alongside business datasets in the same transaction;
do not label independent website/eBay releases as one global batch. Data-health
views must also expose newer failed runs/work/tests while business figures remain
on the last good release; label the health-read timestamp separately. M07 adds
restricted read-only live health views, masking secrets and exposing only needed
operational fields. Existing published source_health alone is not live failure
visibility. Browser refresh remains separate from acquisition/publication.

Power BI alternative: connect the PostgreSQL connector to the same published marts using Import or DirectQuery. Import needs refresh after publication; DirectQuery queries the source when visuals query but still has refresh/cache considerations. An unattended Power BI Service refresh from local PostgreSQL needs a separately configured service/gateway/access path; it is not automatically provided by Airflow.

References: https://docs.streamlit.io/develop/api-reference/connections/st.connections.sqlconnection ; https://learn.microsoft.com/en-us/power-query/connectors/postgresql ; https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-use-directquery .

## A6. Scope boundaries

In scope: ingestion, source contracts, common data definitions, product/status mapping, current-state data, supported observed history, incremental updates, quality checks, audit, exceptions, and recoverable processing.

Small downstream report: demonstrate usability; advanced business analysis belongs to a later DA/BI phase.

Out of scope initially: writing order actions back to marketplaces, inventory synchronization, a complete commerce website, general-ledger accounting, bank settlement reconciliation, profit/ROI, and verified cash-refund reporting.

Optional later extension: an AI investigation agent that explains integration, mapping, or processing problems using read-only evidence tools. It is not required to establish the core problem or to run the pipeline.


