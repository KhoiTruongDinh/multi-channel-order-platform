SELECT (source_created_at AT TIME ZONE 'UTC')::DATE AS activity_date,
       source_system,
       source_account_id,
       currency,
       COUNT(1)::BIGINT AS order_count,
       SUM(source_order_total_amount)::NUMERIC(20,6) AS source_order_total_amount,
       {{ batch_uuid() }} AS published_batch_id
  FROM {{ ref('candidate_daily_orders') }}
 GROUP BY 1, 2, 3, 4
