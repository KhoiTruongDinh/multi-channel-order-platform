WITH lines AS (
    SELECT v.snapshot_id,
           v.source_system,
           v.source_account_id,
           v.order_json,
           item.value AS item_json
      FROM {{ ref('int_website_versions') }} v
      CROSS JOIN LATERAL jsonb_array_elements(v.business_payload->'order_items') AS item(value)
), mapped AS (
    SELECT l.*,
           mapping.id_count,
           mapping.sku_count,
           mapping.id_variant,
           mapping.sku_variant
      FROM lines l
      CROSS JOIN LATERAL (
          SELECT COUNT(*) FILTER (WHERE m.source_variant_id = l.item_json->>'variant_id') AS id_count,
                 COUNT(*) FILTER (WHERE m.source_sku = l.item_json->>'sku_at_purchase') AS sku_count,
                 MIN(m.canonical_variant_id) FILTER (WHERE m.source_variant_id = l.item_json->>'variant_id') AS id_variant,
                 MIN(m.canonical_variant_id) FILTER (WHERE m.source_sku = l.item_json->>'sku_at_purchase') AS sku_variant
            FROM {{ source('configuration', 'product_mapping') }} m
           WHERE m.source_system = l.source_system
             AND m.source_account_id = l.source_account_id
             AND m.mapping_version = '{{ var("mapping_version") }}'
             AND m.mapping_status = 'CONFIRMED'
             AND m.valid_to IS NULL
             AND (m.source_variant_id = l.item_json->>'variant_id'
                  OR m.source_sku = l.item_json->>'sku_at_purchase')
      ) mapping
)
SELECT snapshot_id,
       item_json->>'order_item_id' AS source_line_id,
       NULL::TEXT AS source_listing_id,
       item_json->>'variant_id' AS source_variant_id,
       item_json->>'sku_at_purchase' AS source_sku,
       item_json->>'title_at_purchase' AS source_title,
       CASE WHEN id_count = 1 AND (sku_count = 0 OR (sku_count = 1 AND id_variant = sku_variant)) THEN id_variant
            WHEN id_count = 0 AND sku_count = 1 THEN sku_variant END AS canonical_variant_id,
       CASE WHEN id_count = 1 AND (sku_count = 0 OR (sku_count = 1 AND id_variant = sku_variant)) THEN 'CONFIRMED'
            WHEN id_count = 0 AND sku_count = 1 THEN 'CONFIRMED'
            WHEN id_count = 0 AND sku_count = 0 THEN 'UNMAPPED'
            ELSE 'AMBIGUOUS' END AS mapping_status,
       (item_json->>'quantity')::INTEGER AS quantity,
       (item_json->>'unit_price')::NUMERIC(20,6) AS unit_gross_amount,
       (item_json->>'quantity')::NUMERIC(20,6) *
           (item_json->>'unit_price')::NUMERIC(20,6) AS line_gross_amount,
       (item_json->>'line_discount_amount')::NUMERIC(20,6) AS line_discount_amount,
       (item_json->>'line_tax_amount')::NUMERIC(20,6) AS line_tax_amount,
       order_json->>'currency' AS currency,
       '{}'::JSONB AS fulfillment_evidence
  FROM mapped
