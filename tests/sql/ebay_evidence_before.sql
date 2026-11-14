SELECT DISTINCT v.snapshot_id,r.raw_record_id,
       upper(r.resource_type)::TEXT AS evidence_role,r.byte_sha256 AS resource_fingerprint,
       r.acquired_at AS resource_observed_at
  FROM {{ ref('int_ebay_versions') }} v
  JOIN {{ ref('stg_ebay_observations') }} o
    ON o.source_account_id=v.source_account_id AND o.order_json->>'orderId'=v.order_json->>'orderId'
   AND o.order_json->>'lastModifiedDate'=v.order_json->>'lastModifiedDate'
   AND o.content_fingerprint=v.content_fingerprint
  JOIN {{ source('acquisition','raw_records') }} r ON r.run_id=o.run_id
  JOIN {{ source('operations','batch_inputs') }} i ON i.raw_record_id=r.raw_record_id
   AND i.batch_id='{{ var("batch_id") }}'::UUID
 WHERE r.response_status=200 AND (
       r.raw_record_id=o.raw_record_id OR r.metadata->>'order_raw_id'=o.raw_record_id::TEXT
       OR (r.resource_type='ebay_orders' AND EXISTS (
           SELECT 1 FROM jsonb_array_elements(r.parsed_payload->'orders') x
            WHERE x->>'orderId'=v.order_json->>'orderId'
              AND x->>'lastModifiedDate'=v.order_json->>'lastModifiedDate')))
