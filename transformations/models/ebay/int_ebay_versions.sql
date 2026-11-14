{{ config(materialized='table' if var('delta_mode', false) else 'view') }}
WITH ranked AS (
    SELECT raw_record_id, run_id, source_system, source_account_id, acquired_at, byte_sha256, parsed_payload, order_json, content_fingerprint, shipping_json, shipping_raw_id, shipping_observed_at,
           min(acquired_at) OVER (PARTITION BY source_account_id,order_json->>'orderId',
               order_json->>'lastModifiedDate',content_fingerprint) AS first_observed_at,
           row_number() OVER (PARTITION BY source_account_id,order_json->>'orderId',
               order_json->>'lastModifiedDate',content_fingerprint ORDER BY acquired_at,raw_record_id) AS rank
      FROM {{ ref('stg_ebay_observations') }}
)
SELECT raw_record_id, run_id, source_system, source_account_id, acquired_at, byte_sha256, parsed_payload, order_json, content_fingerprint, shipping_json, shipping_raw_id, shipping_observed_at, first_observed_at, rank, md5(concat_ws(chr(31),source_system,source_account_id,order_json->>'orderId',
           order_json->>'lastModifiedDate',encode(content_fingerprint,'hex')))::UUID AS snapshot_id
  FROM ranked WHERE rank=1
