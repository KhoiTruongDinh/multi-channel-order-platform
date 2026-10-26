SELECT source_system, source_account_id, source_order_id, source_updated_at
  FROM {{ ref('candidate_order_snapshot_history') }}
 GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
