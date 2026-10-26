SELECT 1 AS failure
 WHERE (SELECT COUNT(*) FROM {{ ref('candidate_order_snapshot_history') }}) <> 3
    OR (SELECT COUNT(*) FROM {{ ref('candidate_order_line_snapshot_history') }}) <> 3
    OR EXISTS (
        SELECT 1 FROM {{ ref('candidate_order_line_snapshot_history') }}
         WHERE mapping_status <> 'CONFIRMED'
    )
    OR (SELECT array_agg(cancellation_state ORDER BY source_updated_at)
          FROM {{ ref('candidate_order_snapshot_history') }})
       IS DISTINCT FROM ARRAY['NOT_REQUESTED', 'REQUESTED', 'CANCELED']
    OR (SELECT array_agg(first_observed_at ORDER BY source_updated_at)
          FROM {{ ref('candidate_order_snapshot_history') }})
       IS DISTINCT FROM ARRAY['2026-10-17 09:03:00Z'::TIMESTAMPTZ,
                              '2026-10-17 09:11:00Z'::TIMESTAMPTZ,
                              '2026-10-17 09:15:00Z'::TIMESTAMPTZ]
