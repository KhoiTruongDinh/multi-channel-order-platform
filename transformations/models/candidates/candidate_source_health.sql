SELECT c.source_system,
       c.source_account_id,
       c.stream_name,
       c.completed_window_end,
       p.finished_at AS last_successful_acquisition_at,
       NULL::TIMESTAMPTZ AS last_published_at,
       (SELECT COUNT(*) FROM {{ source('operations', 'processing_work') }} w
         WHERE w.source_system = c.source_system
           AND w.source_account_id = c.source_account_id
           AND w.state IN ('PENDING', 'LEASED'))::BIGINT AS pending_work_count,
       (SELECT COUNT(*) FROM {{ source('operations', 'processing_work') }} w
         WHERE w.source_system = c.source_system
           AND w.source_account_id = c.source_account_id
           AND w.state IN ('FAILED', 'DEAD_LETTER'))::BIGINT AS failed_work_count,
       (SELECT COUNT(*) FROM {{ source('operations', 'data_exceptions') }} e
         WHERE e.source_system = c.source_system
           AND e.source_account_id = c.source_account_id
           AND e.state <> 'RESOLVED'
           AND e.severity = 'BLOCKING')::BIGINT AS open_blocking_exception_count,
       'UNKNOWN'::TEXT AS coverage_state,
       '{{ var("batch_id") }}'::UUID AS published_batch_id
  FROM {{ source('operations', 'extraction_checkpoints') }} c
  JOIN {{ source('operations', 'pipeline_runs') }} p ON p.run_id = c.successful_run_id
 WHERE c.source_system = 'internal_web'
   AND c.source_account_id = 'WEB01'
   AND c.stream_name IN ('orders','orders_polling')
