SELECT source_system,
       source_account_id,
       payment_state,
       fulfillment_state,
       cancellation_state,
       COUNT(*)::BIGINT AS order_count,
       '{{ var("batch_id") }}'::UUID AS published_batch_id
  FROM {{ ref('ebay_candidate_orders_current') }}
 GROUP BY 1, 2, 3, 4, 5
