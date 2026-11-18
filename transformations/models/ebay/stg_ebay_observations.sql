-- Cache recursive order fingerprints once per frozen manifest, including replays.
{{ config(materialized='table') }}
WITH orders AS MATERIALIZED (
    SELECT r.raw_record_id,r.run_id,r.source_system,r.source_account_id,r.acquired_at,
           r.byte_sha256,r.parsed_payload,r.parsed_payload AS order_json,r.resource_type AS order_kind
      FROM {{ source('acquisition','raw_records') }} r
      INNER JOIN {{ source('operations','batch_inputs') }} i USING(raw_record_id)
     WHERE i.batch_id={{ batch_uuid() }} AND r.source_system='ebay_sim'
       AND r.source_account_id='seller_sim_01' AND r.resource_type='ebay_order' AND r.response_status=200
    UNION ALL
    SELECT r.raw_record_id,r.run_id,r.source_system,r.source_account_id,r.acquired_at,
           r.byte_sha256,r.parsed_payload,r.parsed_payload->'orders'->e.element_index AS order_json,r.resource_type AS order_kind
      FROM {{ source('acquisition','raw_records') }} r
      INNER JOIN {{ source('operations','batch_inputs') }} i USING(raw_record_id)
      INNER JOIN {{ source('operations','acquisition_elements') }} e USING(raw_record_id)
     WHERE i.batch_id={{ batch_uuid() }} AND r.source_system='ebay_sim'
       AND r.source_account_id='seller_sim_01' AND r.resource_type='ebay_orders' AND r.response_status=200
)
SELECT r.raw_record_id, r.run_id, r.source_system, r.source_account_id, r.acquired_at, r.byte_sha256, r.parsed_payload,
       r.order_json,
       sha256(convert_to(build.canonical_jsonb_text(build.ebay_canonical_json(r.order_json)), 'UTF8')) AS content_fingerprint,
       CASE WHEN f.metadata->>'request_phase'='fulfillment_collection' THEN
           jsonb_set(f.parsed_payload,'{fulfillments}',coalesce((
               SELECT jsonb_agg(coalesce((
                   SELECT d.parsed_payload FROM {{ source('acquisition','raw_records') }} d
                   INNER JOIN {{ source('operations','batch_inputs') }} di USING(raw_record_id)
                   WHERE di.batch_id={{ batch_uuid() }} AND d.run_id=r.run_id
                     AND d.source_system=r.source_system AND d.source_account_id=r.source_account_id
                     AND d.resource_type='ebay_fulfillment' AND d.response_status=200
                     AND d.metadata->>'order_raw_id'=r.raw_record_id::TEXT
                     AND d.metadata->>'order_id'=r.order_json->>'orderId'
                     AND d.parsed_payload->>'fulfillmentId'=child->>'fulfillmentId'
                   ORDER BY d.acquired_at,d.raw_record_id LIMIT 1
               ),child) ORDER BY n)
               FROM jsonb_array_elements(f.parsed_payload->'fulfillments') WITH ORDINALITY x(child,n)
           ),'[]'::JSONB)) ELSE f.parsed_payload END AS shipping_json,
       f.raw_record_id AS shipping_raw_id,
       f.acquired_at AS shipping_observed_at
  FROM orders r
  INNER JOIN {{ source('acquisition','raw_records') }} f
    ON f.run_id=r.run_id AND f.source_system=r.source_system AND f.source_account_id=r.source_account_id
   AND f.resource_type='ebay_fulfillments'
   AND coalesce(f.metadata->>'order_id',CASE WHEN r.order_kind='ebay_order' THEN r.order_json->>'orderId' END)=r.order_json->>'orderId'
   AND f.metadata->>'order_raw_id'=r.raw_record_id::TEXT AND f.response_status=200
  INNER JOIN {{ source('operations','batch_inputs') }} fi ON fi.raw_record_id=f.raw_record_id AND fi.batch_id={{ batch_uuid() }}
