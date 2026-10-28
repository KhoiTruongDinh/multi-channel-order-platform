WITH allocations AS (
    SELECT o.raw_record_id,o.order_json,f AS fulfillment,a AS allocation
      FROM {{ ref('stg_ebay_observations') }} o,
           jsonb_array_elements(o.shipping_json->'fulfillments') f,
           jsonb_array_elements(f->'lineItems') a
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
  JOIN LATERAL jsonb_array_elements(order_json->'lineItems') l
    ON l->>'lineItemId'=allocation->>'lineItemId'
 GROUP BY raw_record_id,allocation->>'lineItemId',(l->>'quantity')::INTEGER
HAVING sum((allocation->>'quantity')::INTEGER) > (l->>'quantity')::INTEGER
UNION ALL
SELECT min(raw_record_id::TEXT) FROM {{ ref('stg_ebay_observations') }}
 GROUP BY source_account_id,order_json->>'orderId',order_json->>'lastModifiedDate',content_fingerprint
HAVING count(DISTINCT build.ebay_canonical_json(shipping_json))>1
