WITH lines AS (
    SELECT v.*,l AS line FROM {{ ref('int_etsy_versions') }} v,
         jsonb_array_elements(order_json->'transactions') l
), mapped AS (
    SELECT l.*,m.* FROM lines l CROSS JOIN LATERAL (
        SELECT count(*) FILTER (WHERE source_variant_id=line->>'product_id' AND source_listing_id=line->>'listing_id') AS id_count,
               min(canonical_variant_id) FILTER (WHERE source_variant_id=line->>'product_id' AND source_listing_id=line->>'listing_id') AS id_variant,
               count(*) FILTER (WHERE source_sku=line->>'sku') AS sku_count,
               min(canonical_variant_id) FILTER (WHERE source_sku=line->>'sku') AS sku_variant
          FROM {{ source('configuration','product_mapping') }} m
         WHERE m.source_system=l.source_system AND m.source_account_id=l.source_account_id
           AND m.mapping_version='{{ var("mapping_version") }}' AND m.mapping_status='CONFIRMED' AND m.valid_to IS NULL
    ) m
)
SELECT snapshot_id,line->>'transaction_id' AS source_line_id,
       line->>'listing_id' AS source_listing_id,line->>'product_id' AS source_variant_id,
       line->>'sku' AS source_sku,line->>'title' AS source_title,
       CASE WHEN id_count=1 AND (sku_count=0 OR (sku_count=1 AND sku_variant=id_variant)) THEN id_variant
            WHEN id_count=0 AND sku_count=1 THEN sku_variant END AS canonical_variant_id,
       CASE WHEN id_count=1 AND (sku_count=0 OR (sku_count=1 AND sku_variant=id_variant)) THEN 'CONFIRMED'
            WHEN id_count=0 AND sku_count=1 THEN 'CONFIRMED'
            WHEN id_count=0 AND sku_count=0 THEN 'UNMAPPED' ELSE 'AMBIGUOUS' END AS mapping_status,
       (line->>'quantity')::INTEGER AS quantity,
       build.etsy_money(line->'price')::NUMERIC(20,6) AS unit_gross_amount,
       (build.etsy_money(line->'price')*(line->>'quantity')::INTEGER)::NUMERIC(20,6) AS line_gross_amount,
       NULL::NUMERIC(20,6) AS line_discount_amount,NULL::NUMERIC(20,6) AS line_tax_amount,
       line#>>'{price,currency_code}' AS currency,
       jsonb_build_object('receipt_shipments',order_json->'shipments',
                          'paid_timestamp',line->'paid_timestamp','shipped_timestamp',line->'shipped_timestamp') AS fulfillment_evidence
  FROM mapped
