SELECT h.snapshot_id::TEXT AS failure
  FROM {{ ref('candidate_order_snapshot_history') }} h
 WHERE NOT EXISTS (
       SELECT 1 FROM {{ ref('candidate_snapshot_evidence') }} e
        WHERE e.snapshot_id = h.snapshot_id)
UNION ALL
SELECT e.raw_record_id::TEXT
  FROM {{ ref('candidate_snapshot_evidence') }} e
  LEFT JOIN ops.batch_inputs i
    ON i.raw_record_id=e.raw_record_id AND i.batch_id='{{ var("batch_id") }}'::UUID
 WHERE i.raw_record_id IS NULL OR octet_length(e.resource_fingerprint) <> 32
