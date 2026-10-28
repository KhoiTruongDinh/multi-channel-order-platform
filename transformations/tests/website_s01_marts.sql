{{ config(enabled=(var('validation_mode', 's01') == 's01')) }}
SELECT 1 AS failure
 WHERE NOT EXISTS (
        SELECT 1 FROM {{ ref('candidate_order_activity_daily') }}
         WHERE order_count = 1 AND source_order_total_amount = 40.000000
    )
    OR NOT EXISTS (
        SELECT 1 FROM {{ ref('candidate_product_activity_daily') }}
         WHERE canonical_variant_id = 'V001' AND ordered_units = 2
           AND merchandise_amount = 40.000000
    )
