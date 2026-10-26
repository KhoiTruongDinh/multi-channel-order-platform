SELECT v.snapshot_id,
       o.raw_record_id,
       'WEBSITE_RELATIONAL_SNAPSHOT'::TEXT AS evidence_role,
       o.byte_sha256 AS resource_fingerprint,
       o.acquired_at AS resource_observed_at
  FROM {{ ref('int_website_versions') }} v
  JOIN {{ ref('stg_website_observations') }} o
    ON o.source_system = v.source_system
   AND o.source_account_id = v.source_account_id
   AND o.order_json->>'order_id' = v.source_order_id
   AND (o.order_json->>'updated_at')::TIMESTAMPTZ = v.source_updated_at
   AND o.content_fingerprint = v.content_fingerprint
