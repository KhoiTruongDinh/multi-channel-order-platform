-- Expand child arrays once per acquisition, not once per order. Preserve source
-- array order: the unchanged business payload defines source-version identity.
WITH input_raw AS MATERIALIZED (
    SELECT r.raw_record_id,
           r.source_system,
           r.source_account_id,
           r.acquired_at,
           r.byte_sha256,
           r.parsed_payload
      FROM {{ source('acquisition', 'raw_records') }} r
      INNER JOIN {{ source('operations', 'batch_inputs') }} i USING (raw_record_id)
     WHERE i.batch_id = {{ batch_uuid() }}
       AND r.source_system = 'internal_web'
       AND r.resource_type = 'website_order_window'
), expanded AS (
    SELECT r.raw_record_id, r.source_system, r.source_account_id,
           r.acquired_at, r.byte_sha256, order_value AS order_json
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'orders') AS orders(order_value)
{% if var('delta_mode', false) %}
     WHERE EXISTS (SELECT 1 FROM ops.delta_batch_keys k
                    WHERE k.batch_id={{ batch_uuid() }} AND k.source_order_id=order_value->>'order_id')
{% endif %}
), order_items AS (
    SELECT r.raw_record_id, x.value->>'order_id' AS order_id,
           jsonb_agg(x.value ORDER BY x.position) AS children
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'order_items')
           WITH ORDINALITY AS x(value, position)
     GROUP BY r.raw_record_id, x.value->>'order_id'
), payments AS (
    SELECT r.raw_record_id, x.value->>'order_id' AS order_id,
           jsonb_agg(x.value ORDER BY x.position) AS children
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'payment_transactions')
           WITH ORDINALITY AS x(value, position)
     GROUP BY r.raw_record_id, x.value->>'order_id'
), cancellations AS (
    SELECT r.raw_record_id, x.value->>'order_id' AS order_id,
           jsonb_agg(x.value ORDER BY x.position) AS children
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'cancellation_requests')
           WITH ORDINALITY AS x(value, position)
     GROUP BY r.raw_record_id, x.value->>'order_id'
), shipment_rows AS MATERIALIZED (
    SELECT r.raw_record_id, x.value, x.position,
           x.value->>'order_id' AS order_id,
           x.value->>'shipment_id' AS shipment_id
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'shipments')
           WITH ORDINALITY AS x(value, position)
), shipments AS (
    SELECT raw_record_id, order_id,
           jsonb_agg(value ORDER BY position) AS children
      FROM shipment_rows
     GROUP BY raw_record_id, order_id
), shipment_orders AS (
    -- Match the old EXISTS semantics even if invalid raw repeats a shipment.
    SELECT raw_record_id, order_id, shipment_id FROM shipment_rows
     GROUP BY raw_record_id, order_id, shipment_id
), shipment_item_rows AS MATERIALIZED (
    -- Prevent a planner-selected join from expanding this array per shipment.
    SELECT r.raw_record_id, x.value, x.position,
           x.value->>'shipment_id' AS shipment_id
      FROM input_raw r
      CROSS JOIN LATERAL jsonb_array_elements(r.parsed_payload->'shipment_items')
           WITH ORDINALITY AS x(value, position)
), shipment_items AS (
    SELECT r.raw_record_id, s.order_id,
           jsonb_agg(r.value ORDER BY r.position) AS children
      FROM shipment_item_rows r
      INNER JOIN shipment_orders s ON s.raw_record_id = r.raw_record_id
                            AND s.shipment_id = r.shipment_id
     GROUP BY r.raw_record_id, s.order_id
), shaped AS (
    SELECT e.raw_record_id, e.source_system, e.source_account_id,
           e.acquired_at, e.byte_sha256, e.order_json,
           jsonb_build_object(
               'orders', jsonb_build_array(e.order_json),
               'order_items', COALESCE(i.children, '[]'::JSONB),
               'payment_transactions', COALESCE(p.children, '[]'::JSONB),
               'cancellation_requests', COALESCE(c.children, '[]'::JSONB),
               'shipments', COALESCE(s.children, '[]'::JSONB),
               'shipment_items', COALESCE(si.children, '[]'::JSONB)
           ) AS business_payload
      FROM expanded e
      LEFT JOIN order_items i ON i.raw_record_id = e.raw_record_id
                            AND i.order_id = e.order_json->>'order_id'
      LEFT JOIN payments p ON p.raw_record_id = e.raw_record_id
                         AND p.order_id = e.order_json->>'order_id'
      LEFT JOIN cancellations c ON c.raw_record_id = e.raw_record_id
                              AND c.order_id = e.order_json->>'order_id'
      LEFT JOIN shipments s ON s.raw_record_id = e.raw_record_id
                          AND s.order_id = e.order_json->>'order_id'
      LEFT JOIN shipment_items si ON si.raw_record_id = e.raw_record_id
                                 AND si.order_id = e.order_json->>'order_id'
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
