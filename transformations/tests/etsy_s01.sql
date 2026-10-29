{{ config(enabled=(var('validation_mode','s01')=='s01' and var('release_source','internal_web')=='etsy_sim')) }}
SELECT 'etsy golden' AS failure
 WHERE (SELECT count(*) FROM {{ ref('etsy_candidate_order_snapshot_history') }})<>1
    OR (SELECT count(*) FROM {{ ref('etsy_candidate_orders_current') }})<>1
    OR (SELECT count(*) FROM {{ ref('etsy_candidate_order_lines_current') }})<>1
    OR NOT EXISTS (SELECT 1 FROM {{ ref('etsy_candidate_orders_current') }}
         WHERE source_order_id='9001001' AND payment_state='PAID' AND fulfillment_state='SHIPPED'
           AND cancellation_state='UNKNOWN' AND source_order_total_amount=22 AND items_gross_amount=22 AND currency='USD')
    OR NOT EXISTS (SELECT 1 FROM {{ ref('etsy_candidate_order_lines_current') }}
         WHERE source_line_id='8001001' AND canonical_variant_id='V002' AND quantity=1 AND line_gross_amount=22)
    OR NOT EXISTS (SELECT 1 FROM {{ ref('etsy_candidate_order_snapshot_history') }}
         WHERE source_created_at='2026-10-17T09:04:00Z'::TIMESTAMPTZ
           AND source_updated_at='2026-10-17T09:05:00Z'::TIMESTAMPTZ
           AND first_observed_at='2026-10-17T09:06:00Z'::TIMESTAMPTZ)
