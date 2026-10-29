SELECT DISTINCT v.snapshot_id,o.raw_record_id,'ETSY_RECEIPT'::TEXT AS evidence_role,
       o.byte_sha256 AS resource_fingerprint,o.acquired_at AS resource_observed_at
  FROM {{ ref('int_etsy_versions') }} v JOIN {{ ref('stg_etsy_observations') }} o
    ON o.source_account_id=v.source_account_id AND o.order_json->>'receipt_id'=v.order_json->>'receipt_id'
   AND o.order_json->>'updated_timestamp'=v.order_json->>'updated_timestamp'
   AND o.content_fingerprint=v.content_fingerprint
