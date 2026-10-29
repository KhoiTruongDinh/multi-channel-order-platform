SELECT o.source_system,
       o.source_account_id,
       o.source_order_id,
       l.source_line_id,
       o.snapshot_id,
       l.source_listing_id,
       l.source_variant_id,
       l.source_sku,
       l.source_title,
       l.canonical_variant_id,
       l.mapping_status,
       l.quantity,
       l.unit_gross_amount,
       l.line_gross_amount,
       l.currency,
       o.published_batch_id
  FROM {{ ref('etsy_candidate_orders_current') }} o
  JOIN {{ ref('etsy_candidate_order_line_snapshot_history') }} l USING (snapshot_id)
