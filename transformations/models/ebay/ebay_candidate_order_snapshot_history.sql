WITH quantities AS (
    SELECT v.*,
           (SELECT sum((l->>'quantity')::INTEGER) FROM jsonb_array_elements(order_json->'lineItems') l) AS ordered,
           (SELECT coalesce(sum((l->>'quantity')::INTEGER),0)
              FROM jsonb_array_elements(shipping_json->'fulfillments') f,
                   jsonb_array_elements(f->'lineItems') l
             WHERE f->>'shippedDate' IS NOT NULL) AS shipped
      FROM {{ ref('int_ebay_versions') }} v
)
SELECT snapshot_id,source_system,source_account_id,order_json->>'orderId' AS source_order_id,
       (order_json->>'creationDate')::TIMESTAMPTZ AS source_created_at,
       (order_json->>'lastModifiedDate')::TIMESTAMPTZ AS source_updated_at,
       first_observed_at,content_fingerprint,
       order_json->>'orderPaymentStatus' AS source_payment_status,
       order_json->>'orderFulfillmentStatus' AS source_fulfillment_status,
       order_json#>>'{cancelStatus,cancelState}' AS source_cancellation_status,
       CASE WHEN order_json->>'orderPaymentStatus'='PAID' THEN 'PAID' ELSE 'UNKNOWN' END AS payment_state,
       CASE WHEN shipped>0 AND shipped<ordered THEN 'PARTIALLY_SHIPPED'
            WHEN shipped=ordered THEN 'SHIPPED'
            WHEN order_json->>'orderFulfillmentStatus'='NOT_STARTED' THEN 'NOT_STARTED'
            ELSE 'UNKNOWN' END AS fulfillment_state,
       CASE WHEN order_json#>>'{cancelStatus,cancelState}'='NONE_REQUESTED' THEN 'NOT_REQUESTED' ELSE 'UNKNOWN' END AS cancellation_state,
       order_json#>>'{pricingSummary,total,currency}' AS currency,
       (order_json#>>'{pricingSummary,priceSubtotal,value}')::NUMERIC(20,6) AS items_gross_amount,
       (order_json#>>'{pricingSummary,priceDiscount,value}')::NUMERIC(20,6) AS discount_amount,
       (order_json#>>'{pricingSummary,deliveryCost,value}')::NUMERIC(20,6) AS shipping_amount,
       (order_json#>>'{pricingSummary,tax,value}')::NUMERIC(20,6) AS tax_amount,
       (order_json#>>'{pricingSummary,total,value}')::NUMERIC(20,6) AS source_order_total_amount,
       '{{ var("mapping_version") }}'::TEXT AS mapping_version,
       '{{ var("transformation_version") }}'::TEXT AS transformation_version,
       '{{ var("batch_id") }}'::UUID AS batch_id
  FROM quantities
