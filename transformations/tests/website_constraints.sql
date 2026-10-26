WITH line_totals AS (
    SELECT snapshot_id, SUM(line_gross_amount) gross,
           SUM(line_discount_amount) discount, SUM(line_tax_amount) tax
      FROM {{ ref('candidate_order_line_snapshot_history') }}
     GROUP BY snapshot_id
)
SELECT h.snapshot_id::TEXT AS failure
  FROM {{ ref('candidate_order_snapshot_history') }} h
  LEFT JOIN line_totals l USING (snapshot_id)
 WHERE l.gross IS DISTINCT FROM h.items_gross_amount
    OR l.discount IS DISTINCT FROM h.discount_amount
    OR l.tax IS DISTINCT FROM h.tax_amount
    OR h.source_order_total_amount <> h.items_gross_amount - h.discount_amount + h.shipping_amount + h.tax_amount
    OR h.source_updated_at < h.source_created_at
    OR h.first_observed_at < h.source_updated_at
    OR h.currency !~ '^[A-Z]{3}$'
    OR h.payment_state NOT IN ('UNPAID','PAID')
    OR h.fulfillment_state NOT IN ('NOT_STARTED','PARTIALLY_SHIPPED','SHIPPED','DELIVERED')
    OR h.cancellation_state NOT IN ('NOT_REQUESTED','REQUESTED','CANCELED')
UNION ALL
SELECT snapshot_id::TEXT
  FROM {{ ref('candidate_order_line_snapshot_history') }}
 WHERE quantity <= 0 OR unit_gross_amount < 0
    OR line_gross_amount <> quantity * unit_gross_amount
    OR line_discount_amount < 0 OR line_discount_amount > line_gross_amount
    OR line_tax_amount < 0
UNION ALL
SELECT snapshot_id::TEXT
  FROM {{ ref('candidate_order_line_snapshot_history') }}
 GROUP BY snapshot_id, source_line_id
HAVING COUNT(*) > 1
