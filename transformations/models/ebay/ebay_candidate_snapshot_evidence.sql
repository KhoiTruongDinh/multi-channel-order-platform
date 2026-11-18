-- Separate equijoins avoid a run-wide cross product filtered by an OR.
WITH observations AS MATERIALIZED (
    SELECT o.source_account_id,o.content_fingerprint,o.run_id,o.raw_record_id,
           o.order_json->>'orderId' AS order_id,
           o.order_json->>'lastModifiedDate' AS modified_at,parent.resource_type AS order_kind
      FROM {{ ref('stg_ebay_observations') }} o
      INNER JOIN {{ source('acquisition','raw_records') }} parent ON parent.raw_record_id=o.raw_record_id
), eligible_raw AS MATERIALIZED (
    SELECT r.raw_record_id,r.run_id,r.resource_type,r.byte_sha256,
           r.acquired_at,r.metadata,r.parsed_payload
      FROM {{ source('acquisition','raw_records') }} r
      INNER JOIN {{ source('operations','batch_inputs') }} i USING(raw_record_id)
     WHERE i.batch_id={{ batch_uuid() }} AND r.response_status=200
       AND EXISTS (SELECT 1 FROM observations o WHERE o.run_id=r.run_id)
), page_orders AS MATERIALIZED (
    -- Expand each relevant list page once, not once per observation candidate.
    SELECT r.raw_record_id,r.run_id,r.resource_type,r.byte_sha256,r.acquired_at,
           x->>'orderId' AS order_id,x->>'lastModifiedDate' AS modified_at
      FROM eligible_raw r CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'orders') x
     WHERE r.resource_type='ebay_orders'
       AND EXISTS (SELECT 1 FROM observations o WHERE o.run_id=r.run_id)
), evidence AS MATERIALIZED (
    -- Resolve raw links before the ranked version join, not once per version.
    SELECT o.source_account_id,o.order_id,o.modified_at,o.content_fingerprint,
           r.raw_record_id,r.resource_type,r.byte_sha256,r.acquired_at
      FROM observations o INNER JOIN eligible_raw r
        ON r.run_id=o.run_id AND r.raw_record_id=o.raw_record_id
    UNION ALL
    SELECT o.source_account_id,o.order_id,o.modified_at,o.content_fingerprint,
           r.raw_record_id,r.resource_type,r.byte_sha256,r.acquired_at
      FROM observations o INNER JOIN eligible_raw r
        ON r.run_id=o.run_id AND r.metadata->>'order_raw_id'=o.raw_record_id::TEXT
       AND coalesce(r.metadata->>'order_id',CASE WHEN o.order_kind='ebay_order' THEN o.order_id END)=o.order_id
    UNION ALL
    SELECT o.source_account_id,o.order_id,o.modified_at,o.content_fingerprint,
           r.raw_record_id,r.resource_type,r.byte_sha256,r.acquired_at
      FROM observations o INNER JOIN page_orders r
        ON r.run_id=o.run_id AND r.order_id=o.order_id AND r.modified_at=o.modified_at
)
SELECT v.snapshot_id,e.raw_record_id,upper(e.resource_type)::TEXT AS evidence_role,
       e.byte_sha256 AS resource_fingerprint,e.acquired_at AS resource_observed_at
  FROM evidence e INNER JOIN {{ ref('int_ebay_versions') }} v
    ON e.source_account_id=v.source_account_id
   AND e.order_id=v.order_json->>'orderId'
   AND e.modified_at=v.order_json->>'lastModifiedDate'
   AND e.content_fingerprint=v.content_fingerprint
 GROUP BY 1, 2, 3, 4, 5
