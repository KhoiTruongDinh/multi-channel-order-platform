WITH h AS (SELECT * FROM {{ ref('etsy_candidate_order_snapshot_history') }}),
     l AS (SELECT * FROM {{ ref('etsy_candidate_order_line_snapshot_history') }})
SELECT 'identity/time/lineage' AS failure FROM h
 WHERE source_order_id IS NULL OR source_created_at IS NULL OR source_updated_at IS NULL
    OR source_updated_at<source_created_at OR first_observed_at<source_updated_at
    OR NOT EXISTS (SELECT 1 FROM {{ ref('etsy_candidate_snapshot_evidence') }} e WHERE e.snapshot_id=h.snapshot_id)
UNION ALL SELECT 'duplicate/conflicting version' FROM h GROUP BY source_system,source_account_id,source_order_id,source_updated_at HAVING count(*)<>1
UNION ALL SELECT 'line identity/grain' FROM l
 WHERE source_line_id IS NULL OR quantity IS NULL OR quantity<=0 OR unit_gross_amount IS NULL
    OR line_gross_amount<>quantity*unit_gross_amount
    OR mapping_status='AMBIGUOUS' OR currency IS NULL
    OR NOT EXISTS (SELECT 1 FROM h WHERE h.snapshot_id=l.snapshot_id AND h.currency=l.currency)
UNION ALL SELECT 'duplicate line' FROM l GROUP BY snapshot_id,source_line_id HAVING count(*)<>1
UNION ALL SELECT 'receipt/transaction mismatch' FROM {{ ref('int_etsy_versions') }} v,
    jsonb_array_elements(order_json->'transactions') t WHERE t->>'receipt_id' IS DISTINCT FROM order_json->>'receipt_id'
UNION ALL SELECT 'missing transactions' FROM {{ ref('int_etsy_versions') }} WHERE jsonb_array_length(order_json->'transactions')=0
UNION ALL SELECT 'currency mismatch' FROM {{ ref('int_etsy_versions') }} v,
    jsonb_each(order_json) m WHERE m.key IN ('total_price','subtotal','grandtotal','discount_amt','total_shipping_cost','total_tax_cost','total_vat_cost','gift_wrap_price')
      AND (build.etsy_money(m.value) IS NOT NULL AND m.value->>'currency_code' IS DISTINCT FROM order_json#>>'{grandtotal,currency_code}')
UNION ALL SELECT 'receipt wire types' FROM {{ ref('int_etsy_versions') }}
 WHERE jsonb_typeof(order_json->'receipt_id') IS DISTINCT FROM 'number'
    OR coalesce(order_json->>'receipt_id','') !~ '^[1-9][0-9]*$'
    OR jsonb_typeof(order_json->'created_timestamp') IS DISTINCT FROM 'number'
    OR jsonb_typeof(order_json->'updated_timestamp') IS DISTINCT FROM 'number'
    OR jsonb_typeof(order_json->'is_paid') IS DISTINCT FROM 'boolean'
    OR jsonb_typeof(order_json->'is_shipped') IS DISTINCT FROM 'boolean'
UNION ALL SELECT 'transaction identity wire type' FROM {{ ref('int_etsy_versions') }} v,
    jsonb_array_elements(order_json->'transactions') t
 WHERE jsonb_typeof(t->'transaction_id') IS DISTINCT FROM 'number'
    OR coalesce(t->>'transaction_id','') !~ '^[1-9][0-9]*$'
