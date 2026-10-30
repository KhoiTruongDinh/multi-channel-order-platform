\set ON_ERROR_STOP on
BEGIN;
-- All synthetic operational probes roll back, leaving business/raw evidence intact.
INSERT INTO ops.pipeline_runs(run_id,stage,source_system,source_account_id,stream_name,
    started_at,finished_at,status,error_message)
VALUES ('07000000-0000-4000-8000-000000000001','RECOVER','etsy_sim','7001','m07_probe',
    statement_timestamp(),statement_timestamp(),'FAILED','SECRET_SENTINEL_MUST_NOT_BE_EXPOSED');
INSERT INTO ops.data_exceptions(exception_id,exception_key,rule_id,severity,state,
    source_system,source_account_id,processing_version,reason,details,first_seen_at,last_seen_at)
VALUES ('07000000-0000-4000-8000-000000000002','m07_rollback_probe','M07_PROBE','BLOCKING','OPEN',
    'etsy_sim','7001','m07-v1','SECRET_SENTINEL_MUST_NOT_BE_EXPOSED',
    '{"password":"SECRET_SENTINEL_MUST_NOT_BE_EXPOSED"}',statement_timestamp(),statement_timestamp());
SET LOCAL ROLE platform_report;
DO $$ DECLARE document TEXT; BEGIN
    IF (SELECT count(*) FROM report.orders_current) <> 3 THEN RAISE EXCEPTION 'order count'; END IF;
    IF (SELECT count(*) FROM report.order_lines_current) <> 4 OR
       (SELECT sum(quantity) FROM report.order_lines_current) <> 6 OR
       (SELECT sum(line_gross_amount) FROM report.order_lines_current) <> 124 THEN
        RAISE EXCEPTION 'line grain/amount';
    END IF;
    IF NOT EXISTS(SELECT FROM report.live_runs WHERE run_id='07000000-0000-4000-8000-000000000001'
                  AND status='FAILED') THEN RAISE EXCEPTION 'live failed run invisible'; END IF;
    IF (SELECT blocking_exception_count FROM report.live_source_health WHERE source_system='etsy_sim')<1 THEN
        RAISE EXCEPTION 'live exception invisible'; END IF;
    SELECT string_agg(to_jsonb(t)::TEXT,'') INTO document FROM report.live_runs t
      WHERE run_id='07000000-0000-4000-8000-000000000001';
    IF document LIKE '%SECRET_SENTINEL%' THEN RAISE EXCEPTION 'run secret exposure'; END IF;
    SELECT string_agg(to_jsonb(t)::TEXT,'') INTO document FROM report.live_exceptions t
      WHERE exception_id='07000000-0000-4000-8000-000000000002';
    IF document LIKE '%SECRET_SENTINEL%' THEN RAISE EXCEPTION 'exception secret exposure'; END IF;
    IF EXISTS(SELECT FROM report.live_source_health WHERE coverage_state<>'UNKNOWN') THEN
        RAISE EXCEPTION 'unsupported coverage'; END IF;
    IF (SELECT count(*) FROM report.order_observed_history)<>6 OR
       (SELECT count(*) FROM report.order_observed_history WHERE source_system='etsy_sim')<>1 THEN
        RAISE EXCEPTION 'observed history'; END IF;
    IF (SELECT count(*) FROM report.line_shipment_allocations)<>1 OR NOT EXISTS(
        SELECT FROM report.line_shipment_allocations WHERE source_system='ebay_sim'
         AND fulfillment_id='FUL001' AND source_line_id='10001001' AND allocated_quantity=2) THEN
        RAISE EXCEPTION 'recorded allocations'; END IF;
    IF has_schema_privilege(current_user,'raw','USAGE') OR
       has_schema_privilege(current_user,'ops','USAGE') OR
       has_table_privilege(current_user,'report.orders_current','UPDATE') THEN
        RAISE EXCEPTION 'report boundary'; END IF;
END $$;
RESET ROLE;
-- Duplicate order ID in another account; missing money and mapping gaps remain
-- visible without multiplying order grain. All synthetic business rows roll back.
INSERT INTO core.order_snapshot_history
SELECT (jsonb_populate_record(NULL::core.order_snapshot_history,to_jsonb(t)||jsonb_build_object(
 'snapshot_id','07000000-0000-4000-8000-000000000003','source_account_id','M07_ACCOUNT'))).*
FROM (SELECT * FROM core.order_snapshot_history WHERE source_system='internal_web' ORDER BY source_updated_at DESC LIMIT 1) t;
INSERT INTO core.orders_current
SELECT (jsonb_populate_record(NULL::core.orders_current,to_jsonb(t)||jsonb_build_object(
 'snapshot_id','07000000-0000-4000-8000-000000000003','source_account_id','M07_ACCOUNT','source_order_total_amount',NULL))).*
FROM (SELECT * FROM core.orders_current WHERE source_system='internal_web' LIMIT 1) t;
INSERT INTO core.order_lines_current
SELECT generated.*
FROM (SELECT * FROM core.order_lines_current WHERE source_system='internal_web' LIMIT 1) t
CROSS JOIN generate_series(1,2) i
CROSS JOIN LATERAL jsonb_populate_record(NULL::core.order_lines_current,to_jsonb(t)||jsonb_build_object(
 'snapshot_id','07000000-0000-4000-8000-000000000003','source_account_id','M07_ACCOUNT',
 'source_line_id','M07_LINE_'||i,'canonical_variant_id',NULL,'mapping_status','UNMAPPED','line_gross_amount',NULL)) generated;
SET LOCAL ROLE platform_report;
DO $$ DECLARE existing_id TEXT; BEGIN
 SELECT source_order_id INTO existing_id FROM report.orders_current WHERE source_system='internal_web' AND source_account_id='WEB01' LIMIT 1;
 IF (SELECT count(*) FROM report.operations_orders WHERE source_system='internal_web' AND source_order_id=existing_id)<>2 THEN
  RAISE EXCEPTION 'account-scoped identity'; END IF;
 IF (SELECT count(*) FROM report.operations_orders WHERE source_account_id='M07_ACCOUNT' AND data_issue)<>1 THEN
  RAISE EXCEPTION 'mapping issue multiplied order grain'; END IF;
 IF (SELECT source_order_total_amount IS NOT NULL FROM report.operations_orders WHERE source_account_id='M07_ACCOUNT') THEN
  RAISE EXCEPTION 'missing order money became zero'; END IF;
 IF (SELECT count(*) FILTER(WHERE line_gross_amount IS NULL) FROM report.order_lines_current WHERE source_account_id='M07_ACCOUNT')<>2 THEN
  RAISE EXCEPTION 'missing line money lost'; END IF;
END $$;
ROLLBACK;
SELECT 'M07 report SQL/role/live-failure/secret-exclusion PASS (probes rolled back)' AS result;
