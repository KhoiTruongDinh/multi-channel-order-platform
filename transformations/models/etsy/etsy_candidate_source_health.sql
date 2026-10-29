SELECT 'etsy_sim'::TEXT AS source_system,'7001'::TEXT AS source_account_id,'receipts'::TEXT AS stream_name,
       (SELECT max(completed_window_end) FROM {{ source('operations','extraction_checkpoints') }} WHERE source_system='etsy_sim' AND source_account_id='7001') AS completed_window_end,
       (SELECT max(finished_at) FROM {{ source('operations','pipeline_runs') }} WHERE source_system='etsy_sim' AND source_account_id='7001' AND stage='ACQUIRE' AND status='SUCCEEDED' AND stream_name IN ('receipt_work','receipts','receipts_polling')) AS last_successful_acquisition_at,
       NULL::TIMESTAMPTZ AS last_published_at,
       (SELECT count(*) FROM {{ source('operations','processing_work') }} WHERE source_system='etsy_sim' AND state IN ('PENDING','LEASED'))::BIGINT AS pending_work_count,
       (SELECT count(*) FROM {{ source('operations','processing_work') }} WHERE source_system='etsy_sim' AND state IN ('FAILED','DEAD_LETTER'))::BIGINT AS failed_work_count,
       (SELECT count(*) FROM {{ source('operations','data_exceptions') }} WHERE source_system='etsy_sim' AND state<>'RESOLVED' AND severity='BLOCKING')::BIGINT AS open_blocking_exception_count,
       'UNKNOWN'::TEXT AS coverage_state,'{{ var("batch_id") }}'::UUID AS published_batch_id
