SELECT (o.source_created_at AT TIME ZONE 'UTC')::DATE AS activity_date,
       l.source_system,
       l.source_account_id,
       COALESCE(l.canonical_variant_id, '__UNMAPPED__') AS product_bucket_key,
       l.canonical_variant_id,
       l.mapping_status,
       l.currency,
       COUNT(1)::BIGINT AS line_count,
       SUM(l.quantity)::BIGINT AS ordered_units,
       SUM(l.line_gross_amount)::NUMERIC(20,6) AS merchandise_amount,
       {{ batch_uuid() }} AS published_batch_id
  FROM {{ effective_current('etsy_candidate_order_lines_current','order_lines_current',['source_system','source_account_id','source_order_id','canonical_variant_id','mapping_status','currency','quantity','line_gross_amount'],order_scope='etsy_candidate_daily_orders') }} l
  INNER JOIN {{ ref('etsy_candidate_daily_orders') }} o
    USING (source_system, source_account_id, source_order_id)
 GROUP BY 1, 2, 3, 4, 5, 6, 7
