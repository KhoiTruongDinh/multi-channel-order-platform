-- Read-only DBeaver inspection. Connect to marketplace_sim.
SELECT d.name,d.campaign_id,d.state,b.published_at,b.shift_seconds,
       d.coverage->'delivery_plan' AS plan
FROM s02.local_datasets d LEFT JOIN s02.live_batches b USING(campaign_id)
WHERE d.coverage#>>'{delivery_plan,version}'='1'
ORDER BY b.published_at DESC NULLS LAST,d.name LIMIT 30;

-- Latest admitted demo only. Change the prefix for another config profile.
WITH chosen AS (
 SELECT d.campaign_id FROM s02.local_datasets d JOIN s02.live_batches b USING(campaign_id)
 WHERE d.name LIKE 'sim-delivery-demo%' ORDER BY b.published_at DESC LIMIT 1
)
SELECT d.receipt_id,d.event_type,d.message_id,d.source_sequence,
       v.source_updated_at,v.visible_at AS source_visible_at,d.omitted,
       s.attempt_no,s.due_at AS planned_due_at,
       s.due_at+make_interval(secs=>b.shift_seconds::double precision) AS effective_due_at,
       s.send_count,s.last_attempt_at,s.next_retry_at,s.completed_at,
       s.last_http_status,s.last_error_code
FROM chosen c JOIN s02.deliveries d USING(campaign_id)
JOIN s02.versions v ON (v.campaign_id,v.source,v.account_id,v.order_id,v.sequence)=
 (d.campaign_id,d.source,d.account_id,d.receipt_id,d.source_sequence)
JOIN s02.live_batches b ON b.campaign_id=d.campaign_id
LEFT JOIN s02.delivery_schedule s ON (s.campaign_id,s.message_id)=(d.campaign_id,d.message_id)
ORDER BY effective_due_at NULLS LAST,d.receipt_id,d.message_id,s.attempt_no;

-- Count parents separately to avoid multiplying by child sends.
WITH chosen AS (
 SELECT d.campaign_id FROM s02.local_datasets d JOIN s02.live_batches b USING(campaign_id)
 WHERE d.name LIKE 'sim-delivery-demo%' ORDER BY b.published_at DESC LIMIT 1
)
SELECT
 (SELECT count(*) FROM s02.deliveries d JOIN chosen USING(campaign_id)) AS logical_messages,
 (SELECT count(*) FROM s02.deliveries d JOIN chosen USING(campaign_id) WHERE omitted) AS omitted_messages,
 (SELECT count(*) FROM s02.delivery_schedule s JOIN chosen USING(campaign_id)) AS planned_sends,
 (SELECT count(*) FROM s02.delivery_schedule s JOIN chosen USING(campaign_id) WHERE completed_at IS NOT NULL) AS completed_sends,
 (SELECT coalesce(sum(send_count),0) FROM s02.delivery_schedule s JOIN chosen USING(campaign_id)) AS actual_send_attempts;
