SELECT r.*, build.etsy_canonical_json(r.parsed_payload) AS order_json,
       sha256(convert_to(build.canonical_jsonb_text(build.etsy_canonical_json(r.parsed_payload)), 'UTF8')) AS content_fingerprint
  FROM {{ source('acquisition','raw_records') }} r
  JOIN {{ source('operations','batch_inputs') }} i USING(raw_record_id)
 WHERE i.batch_id='{{ var("batch_id") }}'::UUID AND r.source_system='etsy_sim'
   AND r.source_account_id='7001' AND r.resource_type='etsy_receipt' AND r.response_status=200
