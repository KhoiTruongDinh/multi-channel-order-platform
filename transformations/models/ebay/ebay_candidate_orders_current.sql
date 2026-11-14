WITH ranked AS (
    SELECT h.source_system, h.source_account_id, h.source_order_id, h.snapshot_id, h.source_created_at, h.source_updated_at, h.first_observed_at, h.content_fingerprint, h.payment_state, h.fulfillment_state, h.cancellation_state, h.currency, h.items_gross_amount, h.source_order_total_amount, h.batch_id,
           ROW_NUMBER() OVER (
               PARTITION BY source_system, source_account_id, source_order_id
               ORDER BY source_updated_at DESC, first_observed_at DESC,
                        encode(content_fingerprint, 'hex') DESC
           ) AS current_rank
      FROM {{ ref('ebay_candidate_order_snapshot_history') }} h
)
SELECT source_system,
       source_account_id,
       source_order_id,
       snapshot_id,
       source_created_at,
       source_updated_at,
       first_observed_at AS source_snapshot_observed_at,
       payment_state,
       fulfillment_state,
       cancellation_state,
       currency,
       items_gross_amount,
       source_order_total_amount,
       batch_id AS published_batch_id
  FROM ranked
 WHERE current_rank = 1
