\set ON_ERROR_STOP on
\timing on
-- Target-query benchmark only. No source simulator/load generator or committed rows.
BEGIN;
SET LOCAL statement_timeout='300s';
SET LOCAL lock_timeout='5s';
DO $$ BEGIN
 IF EXISTS(SELECT FROM core.orders_current WHERE source_order_id LIKE 'M07_SCALE_%') THEN
  RAISE EXCEPTION 'Benchmark ID prefix already exists; refusing to overwrite';
 END IF;
END $$;
INSERT INTO core.order_snapshot_history
SELECT generated.*
FROM (SELECT * FROM core.order_snapshot_history WHERE source_system='internal_web' LIMIT 1) template
CROSS JOIN generate_series(1,100000) i
CROSS JOIN LATERAL jsonb_populate_record(NULL::core.order_snapshot_history,to_jsonb(template)||jsonb_build_object(
 'snapshot_id',md5('M07_SCALE_'||i)::uuid,'source_order_id','M07_SCALE_'||lpad(i::text,6,'0'),
 'content_fingerprint','\x'||md5(i::text)||md5(i::text))) generated;
INSERT INTO core.orders_current
SELECT generated.*
FROM (SELECT * FROM core.orders_current WHERE source_system='internal_web' LIMIT 1) template
CROSS JOIN generate_series(1,100000) i
CROSS JOIN LATERAL jsonb_populate_record(NULL::core.orders_current,to_jsonb(template)||jsonb_build_object(
 'snapshot_id',md5('M07_SCALE_'||i)::uuid,'source_order_id','M07_SCALE_'||lpad(i::text,6,'0'))) generated;
ANALYZE core.orders_current;
ANALYZE core.order_snapshot_history;
SET LOCAL ROLE platform_report;
DO $$ BEGIN
 IF (SELECT count(*) FROM report.operations_orders WHERE source_order_id LIKE 'M07_SCALE_%')<>100000 THEN
  RAISE EXCEPTION 'Synthetic target row count';
 END IF;
END $$;
-- Same seek/filter shape as reports.data.page_query, including review projection.
EXPLAIN (ANALYZE,BUFFERS)
SELECT source_system,source_account_id,source_order_id,source_created_at,
 report.review_reasons(payment_state,fulfillment_state,cancellation_state),data_issue
FROM report.operations_orders o
WHERE (source_system,source_account_id) IN (SELECT * FROM unnest(ARRAY['internal_web'],ARRAY['WEB01']))
 AND currency='USD' AND source_created_at>='2026-10-17T00:00:00Z' AND source_created_at<'2026-10-18T00:00:00Z'
ORDER BY source_created_at DESC,source_system DESC,source_account_id DESC,source_order_id DESC LIMIT 51;
EXPLAIN (ANALYZE,BUFFERS)
SELECT source_order_id,review_reasons,data_issue FROM report.operations_orders
WHERE source_system='internal_web' AND source_account_id='WEB01' AND source_order_id='M07_SCALE_050000';
EXPLAIN (ANALYZE,BUFFERS)
SELECT count(*) FROM report.operations_orders WHERE source_system='internal_web' AND source_account_id='WEB01';
ROLLBACK;
-- Restore accurate planner statistics after the rolled-back synthetic population.
ANALYZE core.orders_current;
ANALYZE core.order_snapshot_history;
DO $$ BEGIN
 IF EXISTS(SELECT FROM core.orders_current WHERE source_order_id LIKE 'M07_SCALE_%') OR
 EXISTS(SELECT FROM core.order_snapshot_history WHERE source_order_id LIKE 'M07_SCALE_%') THEN
  RAISE EXCEPTION 'Benchmark rollback failed';
 END IF;
END $$;
SELECT 'M07 100k target-query benchmark PASS; all synthetic data rolled back' AS result;
