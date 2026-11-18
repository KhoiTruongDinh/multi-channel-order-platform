SELECT v.snapshot_id,o.raw_record_id,upper(r.resource_type)::TEXT AS evidence_role,
       o.byte_sha256 AS resource_fingerprint,o.acquired_at AS resource_observed_at
  FROM {{ ref('int_etsy_versions') }} v INNER JOIN {{ ref('stg_etsy_observations') }} o
    ON o.source_account_id=v.source_account_id AND o.order_json->>'receipt_id'=v.order_json->>'receipt_id'
   AND o.order_json->>'updated_timestamp'=v.order_json->>'updated_timestamp'
   AND o.content_fingerprint=v.content_fingerprint
  INNER JOIN {{ source('acquisition','raw_records') }} r ON r.raw_record_id=o.raw_record_id
 GROUP BY 1, 2, 3, 4, 5
