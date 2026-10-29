SELECT (o.source_created_at AT TIME ZONE 'UTC')::DATE AS activity_date,
       l.source_system,
       l.source_account_id,
       COALESCE(l.canonical_variant_id, '__UNMAPPED__') AS product_bucket_key,
       l.canonical_variant_id,
       l.mapping_status,
       l.currency,
       COUNT(*)::BIGINT AS line_count,
       SUM(l.quantity)::BIGINT AS ordered_units,
       SUM(l.line_gross_amount)::NUMERIC(20,6) AS merchandise_amount,
       '{{ var("batch_id") }}'::UUID AS published_batch_id
  FROM {{ ref('etsy_candidate_order_lines_current') }} l
  JOIN {{ ref('etsy_candidate_orders_current') }} o
    USING (source_system, source_account_id, source_order_id)
 GROUP BY 1, 2, 3, 4, 5, 6, 7
