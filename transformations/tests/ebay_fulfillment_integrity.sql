WITH allocations AS (
    SELECT o.raw_record_id,o.order_json,f AS fulfillment,a AS allocation
      FROM {{ ref('stg_ebay_observations') }} o
      CROSS JOIN LATERAL jsonb_array_elements(o.shipping_json->'fulfillments') f
      CROSS JOIN LATERAL jsonb_array_elements(f->'lineItems') a
)
SELECT raw_record_id::TEXT AS failure
  FROM allocations a
 WHERE NOT EXISTS (SELECT 1 FROM jsonb_array_elements(order_json->'lineItems') l
                    WHERE l->>'lineItemId'=allocation->>'lineItemId')
    OR (allocation->>'quantity')::INTEGER<=0
    OR (fulfillment->>'shippedDate')::TIMESTAMPTZ > (order_json->>'lastModifiedDate')::TIMESTAMPTZ
    OR (fulfillment->>'shippedDate')::TIMESTAMPTZ < (order_json->>'creationDate')::TIMESTAMPTZ
    OR (fulfillment->>'shippedDate' IS NOT NULL AND (
        order_json->>'orderFulfillmentStatus' NOT IN ('IN_PROGRESS','FULFILLED')
        OR EXISTS (SELECT 1 FROM jsonb_array_elements(order_json->'lineItems') l
            WHERE l->>'lineItemId'=allocation->>'lineItemId' AND l->>'lineItemFulfillmentStatus'<>'FULFILLED')))
UNION ALL
SELECT raw_record_id::TEXT FROM allocations
  INNER JOIN LATERAL jsonb_array_elements(order_json->'lineItems') l
    ON l->>'lineItemId'=allocation->>'lineItemId'
 GROUP BY raw_record_id,allocation->>'lineItemId',(l->>'quantity')::INTEGER
HAVING sum((allocation->>'quantity')::INTEGER) > (l->>'quantity')::INTEGER
UNION ALL
SELECT min(raw_record_id)
  FROM (
    SELECT min(raw_record_id::TEXT) AS raw_record_id,source_account_id,
           order_json->>'orderId' AS order_id,
           order_json->>'lastModifiedDate' AS modified_at,content_fingerprint,
           build.ebay_canonical_json(shipping_json) AS shipping_payload
      FROM {{ ref('stg_ebay_observations') }}
     WHERE shipping_json IS NOT NULL
     GROUP BY source_account_id,order_json->>'orderId',
              order_json->>'lastModifiedDate',content_fingerprint,
              build.ebay_canonical_json(shipping_json)
  ) shipping_versions
 GROUP BY source_account_id,order_id,modified_at,content_fingerprint
HAVING count(1)>1
