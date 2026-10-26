\set ON_ERROR_STOP on
SET m02.execution_id TO :'execution_id';

DO $$
DECLARE
    execution text := current_setting('m02.execution_id');
    scheduled_count integer;
    replay_count integer;
    failed_count integer;
    states text[];
BEGIN
    SELECT count(*) FILTER (WHERE r.metadata->>'run_kind' = 'scheduled'),
           count(*) FILTER (WHERE r.metadata->>'run_kind' = 'replay'),
           count(*) FILTER (WHERE p.status = 'FAILED')
      INTO scheduled_count, replay_count, failed_count
      FROM raw.raw_records r
      JOIN ops.pipeline_runs p USING (run_id)
     WHERE r.metadata->>'execution_id' = execution;

    IF scheduled_count <> 3 OR replay_count <> 1 OR failed_count <> 1 THEN
        RAISE EXCEPTION 'unexpected audit counts: scheduled %, replay %, failed %',
            scheduled_count, replay_count, failed_count;
    END IF;

    SELECT array_agg(r.parsed_payload->'orders'->0->>'cancellation_status' ORDER BY r.acquired_at)
      INTO states
      FROM raw.raw_records r
      JOIN ops.pipeline_runs p USING (run_id)
     WHERE r.metadata->>'execution_id' = execution
       AND r.metadata->>'run_kind' = 'scheduled'
       AND p.status = 'SUCCEEDED';
    IF states <> ARRAY['NOT_REQUESTED', 'REQUESTED', 'CANCELED'] THEN
        RAISE EXCEPTION 'scheduled observations differ: %', states;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM ops.extraction_checkpoints c
          JOIN ops.pipeline_runs p ON p.run_id = c.successful_run_id
         WHERE p.log_reference = 'm02:' || execution || ':failure-test'
    ) THEN
        RAISE EXCEPTION 'failed run falsely completed checkpoint';
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM ops.extraction_checkpoints c
          JOIN ops.pipeline_runs p ON p.run_id = c.successful_run_id
         WHERE c.source_system = 'internal_web'
           AND c.source_account_id = 'WEB01'
           AND c.stream_name = 'orders'
           AND c.completed_window_end = TIMESTAMPTZ '2026-10-17 09:15:00Z'
           AND p.log_reference = 'm02:' || execution || ':replay'
    ) THEN
        RAISE EXCEPTION 'replay audit/checkpoint missing';
    END IF;

    IF has_table_privilege('website_reader', 'raw.raw_records', 'SELECT') THEN
        RAISE EXCEPTION 'website reader unexpectedly crosses into platform raw';
    END IF;
END $$;

SELECT 'M02 website acquisition PASS' AS result;
