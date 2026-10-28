{{ config(enabled=(var('validation_mode', 's01') == 's01')) }}
{% if var('release_source', 'internal_web') == 'ebay_sim' %}
SELECT 'eBay S01 count/state/allocation' AS failure
 WHERE (SELECT count(*) FROM {{ ref('ebay_candidate_order_snapshot_history') }})<>2
    OR (SELECT count(*) FROM {{ ref('ebay_candidate_order_line_snapshot_history') }})<>4
    OR (SELECT count(*) FROM {{ ref('ebay_candidate_orders_current') }})<>1
    OR (SELECT count(*) FROM {{ ref('ebay_candidate_order_lines_current') }})<>2
    OR NOT EXISTS (SELECT 1 FROM {{ ref('ebay_candidate_orders_current') }}
        WHERE source_order_id='12-10001-10001' AND payment_state='PAID'
          AND fulfillment_state='PARTIALLY_SHIPPED' AND cancellation_state='NOT_REQUESTED'
          AND items_gross_amount=62 AND source_order_total_amount=62 AND currency='USD')
    OR (SELECT sum(quantity) FROM {{ ref('ebay_candidate_order_lines_current') }})<>3
    OR (SELECT sum(line_gross_amount) FROM {{ ref('ebay_candidate_order_lines_current') }})<>62
    OR NOT EXISTS (SELECT 1 FROM {{ ref('ebay_candidate_order_line_snapshot_history') }}
        WHERE source_line_id='10001001' AND canonical_variant_id='V001' AND quantity=2 AND line_gross_amount=40
          AND fulfillment_evidence#>>'{fulfillments,0,fulfillmentId}'='FUL001'
          AND fulfillment_evidence#>>'{fulfillments,0,lineItems,0,quantity}'='2')
    OR EXISTS (SELECT 1 FROM {{ ref('ebay_candidate_order_line_snapshot_history') }}
        WHERE source_line_id='10001002' AND fulfillment_evidence->'fulfillments'<>'[]'::JSONB)
{% else %}
SELECT 1 AS failure WHERE FALSE
{% endif %}
