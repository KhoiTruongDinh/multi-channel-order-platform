WITH ranked AS (
    SELECT *,
           MIN(acquired_at) OVER (
               PARTITION BY source_system, source_account_id, order_json->>'order_id',
                            order_json->>'updated_at', content_fingerprint
           ) AS first_observed_at,
           ROW_NUMBER() OVER (
               PARTITION BY source_system, source_account_id, order_json->>'order_id',
                            order_json->>'updated_at', content_fingerprint
               ORDER BY acquired_at, raw_record_id
           ) AS duplicate_rank
      FROM {{ ref('stg_website_observations') }}
)
SELECT md5(concat_ws(chr(31), source_system, source_account_id,
                     order_json->>'order_id', order_json->>'updated_at',
                     encode(content_fingerprint, 'hex')))::UUID AS snapshot_id,
       source_system,
       source_account_id,
       order_json->>'order_id' AS source_order_id,
       (order_json->>'created_at')::TIMESTAMPTZ AS source_created_at,
       (order_json->>'updated_at')::TIMESTAMPTZ AS source_updated_at,
       first_observed_at,
       content_fingerprint,
       order_json,
       business_payload
  FROM ranked
 WHERE duplicate_rank = 1
