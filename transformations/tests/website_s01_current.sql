SELECT 1 AS failure
 WHERE (SELECT COUNT(*) FROM {{ ref('candidate_orders_current') }}) <> 1
    OR (SELECT COUNT(*) FROM {{ ref('candidate_order_lines_current') }}) <> 1
    OR NOT EXISTS (
        SELECT 1
          FROM {{ ref('candidate_orders_current') }} o
          JOIN {{ ref('candidate_order_lines_current') }} l
            USING (source_system, source_account_id, source_order_id)
         WHERE o.source_order_id = 'W1001'
           AND o.payment_state = 'PAID'
           AND o.fulfillment_state = 'NOT_STARTED'
           AND o.cancellation_state = 'CANCELED'
           AND o.source_order_total_amount = 40.000000
           AND l.quantity = 2
           AND l.line_gross_amount = 40.000000
           AND l.currency = 'USD'
    )
