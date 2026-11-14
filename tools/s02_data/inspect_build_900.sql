-- Historical UNCHANGED900 review, not a benchmark or pipeline execution.
-- Read-only; timestamp bounds match the saved campaign's admission/finish.
BEGIN READ ONLY;
WITH samples AS (
 SELECT m.source_system,m.measurement_id,m.run_id,p.batch_id,a.attempt_number,
        m.started_at,m.finished_at,m.duration_ms/1000.0 AS stage_seconds,r.results
 FROM ops.execution_measurements m
 JOIN ops.pipeline_runs p USING(run_id)
 JOIN ops.task_attempts a USING(attempt_id)
 JOIN ops.delta_results r ON r.batch_id=p.batch_id AND r.attempt_number=a.attempt_number
 JOIN ops.delta_batches d ON d.batch_id=r.batch_id AND d.plan_sha256=r.plan_sha256
 WHERE m.stage='build_and_test' AND m.outcome='SUCCEEDED' AND r.passed
   AND NOT d.bootstrap
   AND m.started_at>='2026-11-13T14:52:56.547078Z'::timestamptz
   AND m.finished_at<='2026-11-13T15:04:46.054387Z'::timestamptz
), nodes AS (
 SELECT s.source_system,s.measurement_id,s.batch_id,k.kind,
        n->>'id' AS node_id,(n->>'seconds')::double precision AS seconds,
        (n->>'rows')::bigint AS rows
 FROM samples s CROSS JOIN (VALUES ('models'),('tests')) k(kind)
 CROSS JOIN LATERAL jsonb_array_elements(s.results->k.kind) n
), cycles AS (
 SELECT s.source_system,s.batch_id,s.attempt_number,s.started_at,s.stage_seconds,
        coalesce(sum(n.seconds) FILTER(WHERE n.kind='models'),0) AS model_seconds,
        coalesce(sum(n.seconds) FILTER(WHERE n.kind='tests'),0) AS test_seconds,
        s.stage_seconds-coalesce(sum(n.seconds),0) AS unitemized_seconds,
        (SELECT count(*) FROM ops.delta_batch_keys x WHERE x.batch_id=s.batch_id) AS affected_orders,
        (SELECT count(*) FROM ops.delta_new_inputs x WHERE x.batch_id=s.batch_id) AS new_raw,
        (SELECT count(*) FROM ops.batch_inputs x WHERE x.batch_id=s.batch_id) AS context_raw
 FROM samples s LEFT JOIN nodes n USING(measurement_id)
 GROUP BY s.source_system,s.batch_id,s.attempt_number,s.started_at,s.stage_seconds
), summaries AS (
 SELECT source_system,count(*) AS samples,
        percentile_cont(.5) WITHIN GROUP(ORDER BY stage_seconds) AS p50_stage_seconds,
        percentile_cont(.95) WITHIN GROUP(ORDER BY stage_seconds) AS p95_stage_seconds,
        max(stage_seconds) AS max_stage_seconds,
        avg(model_seconds) AS mean_model_seconds,avg(test_seconds) AS mean_test_seconds,
        avg(unitemized_seconds) AS mean_unitemized_seconds,
        sum(model_seconds) AS total_model_seconds,sum(test_seconds) AS total_test_seconds,
        sum(unitemized_seconds) AS total_unitemized_seconds
 FROM cycles GROUP BY source_system
), node_summary AS (
 SELECT source_system,kind,node_id,count(*) AS samples,avg(seconds) AS mean_seconds,
        percentile_cont(.95) WITHIN GROUP(ORDER BY seconds) AS p95_seconds,
        max(seconds) AS max_seconds,sum(seconds) AS total_seconds,max(rows) AS max_rows
 FROM nodes GROUP BY source_system,kind,node_id
)
SELECT jsonb_build_object(
 'scope','Historical successful nonbootstrap build stages inside saved900 window; concurrent retained stack, not only campaign orders',
 'window_start','2026-11-13T14:52:56.547078Z','window_end','2026-11-13T15:04:46.054387Z',
 'summary',(SELECT jsonb_agg(to_jsonb(s) ORDER BY source_system) FROM summaries s),
 'nodes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY source_system,total_seconds DESC) FROM node_summary n),
 'cycles',(SELECT jsonb_agg(to_jsonb(c) ORDER BY stage_seconds DESC) FROM cycles c));
ROLLBACK;
