-- These assertions are scoped to eBay; website money/status rules stay separate.
SELECT snapshot_id::TEXT AS failure
  FROM {{ ref('ebay_candidate_order_snapshot_history') }}
 GROUP BY snapshot_id HAVING count(*)<>1
UNION ALL
SELECT min(snapshot_id::TEXT)
  FROM {{ ref('ebay_candidate_order_snapshot_history') }}
 GROUP BY source_system,source_account_id,source_order_id,source_updated_at HAVING count(*)>1
UNION ALL
SELECT h.snapshot_id::TEXT
  FROM {{ ref('ebay_candidate_order_snapshot_history') }} h
 WHERE h.source_created_at>h.source_updated_at OR h.source_updated_at>h.first_observed_at
    OR h.currency !~ '^[A-Z]{3}$' OR octet_length(h.content_fingerprint)<>32
    OR h.items_gross_amount IS DISTINCT FROM (
        SELECT sum(l.line_gross_amount) FROM {{ ref('ebay_candidate_order_line_snapshot_history') }} l
         WHERE l.snapshot_id=h.snapshot_id)
    OR NOT EXISTS (SELECT 1 FROM {{ ref('ebay_candidate_snapshot_evidence') }} e WHERE e.snapshot_id=h.snapshot_id)
UNION ALL
SELECT l.snapshot_id::TEXT
  FROM {{ ref('ebay_candidate_order_line_snapshot_history') }} l
  JOIN {{ ref('ebay_candidate_order_snapshot_history') }} h USING(snapshot_id)
 WHERE l.quantity<=0 OR l.currency<>h.currency OR l.line_gross_amount<0
    OR l.mapping_status<>'CONFIRMED' OR l.canonical_variant_id IS NULL
UNION ALL
SELECT snapshot_id::TEXT FROM {{ ref('ebay_candidate_order_line_snapshot_history') }}
 GROUP BY snapshot_id,source_line_id HAVING count(*)>1
