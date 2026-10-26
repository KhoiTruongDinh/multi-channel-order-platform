\set ON_ERROR_STOP on
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT batch_id, published_at, transformation_version, mapping_version
  FROM report.publication_state WHERE publication_name='website_orders';
SELECT source_system, source_account_id, source_order_id, payment_state,
       fulfillment_state, cancellation_state, source_order_total_amount
  FROM report.orders_current WHERE source_system='internal_web';
SELECT source_system, source_account_id, source_order_id, source_line_id,
       canonical_variant_id, quantity, line_gross_amount, currency
  FROM report.order_lines_current WHERE source_system='internal_web';
SELECT activity_date, order_count, source_order_total_amount
  FROM report.order_activity_daily WHERE source_system='internal_web';
SELECT canonical_variant_id, ordered_units, merchandise_amount
  FROM report.product_activity_daily WHERE source_system='internal_web';
COMMIT;
