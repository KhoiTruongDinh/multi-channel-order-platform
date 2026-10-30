\set ON_ERROR_STOP on
BEGIN;
CREATE OR REPLACE VIEW report.order_observed_history AS
SELECT h.snapshot_id,h.source_system,h.source_account_id,h.source_order_id,
       h.source_updated_at,h.first_observed_at,h.payment_state,h.fulfillment_state,
       h.cancellation_state,h.currency,h.source_order_total_amount
FROM core.order_snapshot_history h;

-- Project only recorded eBay allocation fields; do not invent an Etsy bridge.
CREATE OR REPLACE VIEW report.line_shipment_allocations AS
SELECT c.source_system,c.source_account_id,c.source_order_id,c.source_line_id,
       f->>'fulfillmentId' AS fulfillment_id,f->>'shippedDate' AS shipped_at,
       (a->>'quantity')::INTEGER AS allocated_quantity,f->>'shippingCarrierCode' AS carrier
FROM core.order_lines_current c
JOIN core.order_line_snapshot_history h USING(snapshot_id,source_line_id)
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(h.fulfillment_evidence->'fulfillments','[]'::JSONB)) f
CROSS JOIN LATERAL jsonb_array_elements(COALESCE(f->'lineItems','[]'::JSONB)) a
WHERE c.source_system='ebay_sim' AND a->>'lineItemId'=c.source_line_id;

REVOKE ALL ON report.order_observed_history,report.line_shipment_allocations FROM PUBLIC;
GRANT SELECT ON report.order_observed_history,report.line_shipment_allocations TO platform_report;
INSERT INTO public.schema_migrations(migration_name)
VALUES ('platform/007_report_order_detail.sql') ON CONFLICT DO NOTHING;
COMMIT;
