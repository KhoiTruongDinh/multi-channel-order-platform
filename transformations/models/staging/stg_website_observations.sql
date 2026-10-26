WITH input_raw AS (
    SELECT r.raw_record_id,
           r.source_system,
           r.source_account_id,
           r.acquired_at,
           r.byte_sha256,
           r.parsed_payload
      FROM {{ source('acquisition', 'raw_records') }} r
      JOIN {{ source('operations', 'batch_inputs') }} i USING (raw_record_id)
     WHERE i.batch_id = '{{ var("batch_id") }}'::UUID
       AND r.source_system = 'internal_web'
       AND r.resource_type = 'website_order_window'
), expanded AS (
    SELECT r.*,
           order_value AS order_json
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'orders') AS orders(order_value)
), shaped AS (
    SELECT e.*,
           jsonb_build_object(
               'orders', jsonb_build_array(e.order_json),
               'order_items', COALESCE((
                   SELECT jsonb_agg(x.value ORDER BY x.position)
                     FROM jsonb_array_elements(e.parsed_payload->'order_items') WITH ORDINALITY AS x(value, position)
                    WHERE x.value->>'order_id' = e.order_json->>'order_id'
               ), '[]'::JSONB),
               'payment_transactions', COALESCE((
                   SELECT jsonb_agg(x.value ORDER BY x.position)
                     FROM jsonb_array_elements(e.parsed_payload->'payment_transactions') WITH ORDINALITY AS x(value, position)
                    WHERE x.value->>'order_id' = e.order_json->>'order_id'
               ), '[]'::JSONB),
               'cancellation_requests', COALESCE((
                   SELECT jsonb_agg(x.value ORDER BY x.position)
                     FROM jsonb_array_elements(e.parsed_payload->'cancellation_requests') WITH ORDINALITY AS x(value, position)
                    WHERE x.value->>'order_id' = e.order_json->>'order_id'
               ), '[]'::JSONB),
               'shipments', COALESCE((
                   SELECT jsonb_agg(x.value ORDER BY x.position)
                     FROM jsonb_array_elements(e.parsed_payload->'shipments') WITH ORDINALITY AS x(value, position)
                    WHERE x.value->>'order_id' = e.order_json->>'order_id'
               ), '[]'::JSONB),
               'shipment_items', COALESCE((
                   SELECT jsonb_agg(x.value ORDER BY x.position)
                     FROM jsonb_array_elements(e.parsed_payload->'shipment_items') WITH ORDINALITY AS x(value, position)
                    WHERE EXISTS (
                        SELECT 1
                          FROM jsonb_array_elements(e.parsed_payload->'shipments') AS s(value)
                         WHERE s.value->>'order_id' = e.order_json->>'order_id'
                           AND s.value->>'shipment_id' = x.value->>'shipment_id'
                    )
               ), '[]'::JSONB)
           ) AS business_payload
      FROM expanded e
)
SELECT raw_record_id,
       source_system,
       source_account_id,
       acquired_at,
       byte_sha256,
       order_json,
       business_payload,
       sha256(convert_to(build.canonical_jsonb_text(business_payload), 'UTF8')) AS content_fingerprint
  FROM shaped
