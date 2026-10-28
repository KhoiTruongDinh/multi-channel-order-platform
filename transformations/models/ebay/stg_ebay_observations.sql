-- Cache recursive order fingerprints once per frozen manifest, including replays.
{{ config(materialized='table') }}
SELECT r.*,
       r.parsed_payload AS order_json,
       sha256(convert_to(build.canonical_jsonb_text(build.ebay_canonical_json(r.parsed_payload)), 'UTF8')) AS content_fingerprint,
       f.parsed_payload AS shipping_json,
       f.raw_record_id AS shipping_raw_id,
       f.acquired_at AS shipping_observed_at
  FROM {{ source('acquisition','raw_records') }} r
  JOIN {{ source('operations','batch_inputs') }} i USING (raw_record_id)
  JOIN {{ source('acquisition','raw_records') }} f
    ON f.run_id=r.run_id AND f.resource_type='ebay_fulfillments'
   AND f.metadata->>'order_raw_id'=r.raw_record_id::TEXT AND f.response_status=200
  JOIN {{ source('operations','batch_inputs') }} fi ON fi.raw_record_id=f.raw_record_id AND fi.batch_id=i.batch_id
 WHERE i.batch_id='{{ var("batch_id") }}'::UUID
   AND r.source_system='ebay_sim' AND r.source_account_id='seller_sim_01'
   AND r.resource_type='ebay_order' AND r.response_status=200
