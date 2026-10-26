\set ON_ERROR_STOP on
SET m03.published_batch_id TO :'published_batch_id';
SET m03.failed_batch_id TO :'failed_batch_id';

DO $$
DECLARE
    published_batch UUID := current_setting('m03.published_batch_id')::UUID;
    failed_batch UUID := current_setting('m03.failed_batch_id')::UUID;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM ops.publication_state
         WHERE publication_name = 'website_orders'
           AND batch_id = published_batch
           AND mapping_version = 's01-v1'
           AND transformation_version = 'm03-v1'
    ) THEN
        RAISE EXCEPTION 'website publication does not point to tested batch';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM ops.transform_batches WHERE batch_id=published_batch AND status='PUBLISHED')
       OR NOT EXISTS (SELECT 1 FROM ops.transform_batches WHERE batch_id=failed_batch AND status='FAILED') THEN
        RAISE EXCEPTION 'published/failed batch states are incorrect';
    END IF;
    IF (SELECT count(*) FROM core.order_snapshot_history WHERE source_system='internal_web') <> 3 THEN
        RAISE EXCEPTION 'website history must contain exactly three observed versions';
    END IF;
    IF (SELECT count(*) FROM core.order_line_snapshot_history l JOIN core.order_snapshot_history h USING(snapshot_id) WHERE h.source_system='internal_web') <> 3 THEN
        RAISE EXCEPTION 'website line history must contain three parent-observed rows';
    END IF;
    IF (SELECT count(*) FROM core.orders_current WHERE source_system='internal_web') <> 1
       OR (SELECT count(*) FROM core.order_lines_current WHERE source_system='internal_web') <> 1 THEN
        RAISE EXCEPTION 'website current grains are incorrect';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM core.orders_current o
        JOIN core.order_lines_current l USING(source_system, source_account_id, source_order_id)
        WHERE o.source_system='internal_web' AND o.source_order_id='W1001'
          AND o.payment_state='PAID' AND o.fulfillment_state='NOT_STARTED'
          AND o.cancellation_state='CANCELED'
          AND o.source_order_total_amount=40.000000
          AND l.quantity=2 AND l.line_gross_amount=40.000000 AND l.currency='USD'
    ) THEN
        RAISE EXCEPTION 'website current facts differ from S01';
    END IF;
    IF EXISTS (SELECT 1 FROM core.order_snapshot_history WHERE batch_id <> published_batch)
       OR EXISTS (SELECT 1 FROM core.orders_current WHERE published_batch_id <> published_batch)
       OR EXISTS (SELECT 1 FROM mart.order_activity_daily WHERE published_batch_id <> published_batch) THEN
        RAISE EXCEPTION 'failed build changed the stable publication';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mart.order_activity_daily WHERE order_count=1 AND source_order_total_amount=40.000000)
       OR NOT EXISTS (SELECT 1 FROM mart.product_activity_daily WHERE canonical_variant_id='V001' AND ordered_units=2 AND merchandise_amount=40.000000)
       OR NOT EXISTS (SELECT 1 FROM mart.order_status_current WHERE payment_state='PAID' AND fulfillment_state='NOT_STARTED' AND cancellation_state='CANCELED' AND order_count=1) THEN
        RAISE EXCEPTION 'website marts differ from S01';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM mart.source_health WHERE source_system='internal_web' AND coverage_state='UNKNOWN' AND published_batch_id=published_batch) THEN
        RAISE EXCEPTION 'website source health is missing';
    END IF;
END $$;

SELECT 'M03 website dbt/release PASS' AS result;
