SELECT source_system,
       source_account_id,
       payment_state,
       fulfillment_state,
       cancellation_state,
       COUNT(1)::BIGINT AS order_count,
       {{ batch_uuid() }} AS published_batch_id
  FROM {{ effective_current('ebay_candidate_orders_current','orders_current',['source_system','source_account_id','payment_state','fulfillment_state','cancellation_state']) }}
 GROUP BY 1, 2, 3, 4, 5
