{% macro batch_uuid() -%}
{% if var('delta_mode', false) %}current_setting('platform.batch_id')::UUID
{% else %}'{{ var("batch_id") }}'::UUID{% endif %}
{%- endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
{% if var('delta_mode', false) %}
{{ {'internal_web':'build_delta_web','ebay_sim':'build_delta_ebay','etsy_sim':'build_delta_etsy'}[var('release_source')] }}
{% else %}{{ target.schema if custom_schema_name is none else target.schema ~ '_' ~ custom_schema_name | trim }}{% endif %}
{%- endmacro %}

{% macro effective_current(candidate, table, columns, order_scope=none) -%}
{% if not var('delta_mode', false) %}{{ ref(candidate) }}
{% else %}
(SELECT {% for column in columns %}p.{{ column }}{{ ', ' if not loop.last }}{% endfor %} FROM core.{{ table }} p
 WHERE p.source_system='{{ var("release_source") }}'
   AND p.source_account_id='{{ {'internal_web':'WEB01','ebay_sim':'seller_sim_01','etsy_sim':'7001'}[var("release_source")] }}'
   AND NOT EXISTS (SELECT 1 FROM ops.delta_batch_keys k WHERE k.batch_id={{ batch_uuid() }}
                   AND k.source_order_id=p.source_order_id)
{% if order_scope %}
   AND EXISTS (SELECT 1 FROM {{ ref(order_scope) }} d
                WHERE (d.source_system,d.source_account_id,d.source_order_id)=
                      (p.source_system,p.source_account_id,p.source_order_id))
{% endif %}
 UNION ALL SELECT {% for column in columns %}c.{{ column }}{{ ', ' if not loop.last }}{% endfor %}
 FROM {{ ref(candidate) }} c
{% if order_scope %}
 WHERE EXISTS (SELECT 1 FROM {{ ref(order_scope) }} d
                WHERE (d.source_system,d.source_account_id,d.source_order_id)=
                      (c.source_system,c.source_account_id,c.source_order_id))
{% endif %})
{% endif %}
{%- endmacro %}

{% macro activity_scope(orders, source, account) %}
SELECT activity_date,source_system,source_account_id,{{ batch_uuid() }} AS batch_id
FROM (
 SELECT (source_created_at AT TIME ZONE 'UTC')::DATE AS activity_date,
        source_system,source_account_id FROM {{ ref(orders) }}
{% if var('delta_mode', false) %}
 UNION ALL
 SELECT (o.source_created_at AT TIME ZONE 'UTC')::DATE,o.source_system,o.source_account_id
 FROM core.orders_current o INNER JOIN ops.delta_batch_keys k
   ON k.source_order_id=o.source_order_id AND k.batch_id={{ batch_uuid() }}
 WHERE o.source_system='{{ source }}' AND o.source_account_id='{{ account }}'
 UNION ALL
 SELECT activity_date,source_system,source_account_id FROM mart.order_activity_daily
 WHERE source_system='{{ source }}' AND source_account_id='{{ account }}'
   AND current_setting('platform.delta_bootstrap',true)='true'
 UNION ALL
 SELECT activity_date,source_system,source_account_id FROM mart.product_activity_daily
 WHERE source_system='{{ source }}' AND source_account_id='{{ account }}'
   AND current_setting('platform.delta_bootstrap',true)='true'
{% endif %}
) dates
GROUP BY activity_date,source_system,source_account_id
{% endmacro %}

{% macro daily_orders(orders, scope) %}
SELECT o.source_system,o.source_account_id,o.source_order_id,o.source_created_at,
       o.currency,o.source_order_total_amount
FROM {{ effective_current(orders,'orders_current',[
 'source_system','source_account_id','source_order_id','source_created_at',
 'currency','source_order_total_amount']) }} o
INNER JOIN {{ ref(scope) }} d
 ON d.source_system=o.source_system AND d.source_account_id=o.source_account_id
AND o.source_created_at >= (d.activity_date::TIMESTAMP AT TIME ZONE 'UTC')
AND o.source_created_at < ((d.activity_date+1)::TIMESTAMP AT TIME ZONE 'UTC')
{% endmacro %}

{% macro delta_route_sql() %}
-- Operational identity index only. No golden data, status or money transformation.
WITH candidates AS MATERIALIZED (
 SELECT r.raw_record_id,r.run_id,r.source_system,r.source_account_id,
        r.resource_type,r.parsed_payload,r.metadata FROM raw.raw_records r INNER JOIN ops.pipeline_runs p USING(run_id)
 WHERE p.status='SUCCEEDED' AND r.source_system='{{ var("release_source") }}'
   AND r.source_account_id='{{ {'internal_web':'WEB01','ebay_sim':'seller_sim_01','etsy_sim':'7001'}[var("release_source")] }}'
   AND r.resource_type IN
   {% if var('release_source')=='internal_web' %}('website_order_window')
   {% elif var('release_source')=='ebay_sim' %}('ebay_orders','ebay_order','ebay_fulfillments','ebay_fulfillment')
   {% else %}('etsy_receipt'){% endif %}
   {% if var('release_source')!='internal_web' %}AND r.response_status=200{% endif %}
   AND NOT EXISTS (SELECT 1 FROM ops.delta_raw_keys k WHERE k.raw_record_id=r.raw_record_id)
), routed AS (
 SELECT r.raw_record_id,r.source_system,r.source_account_id,x,
 {% if var('release_source')=='internal_web' %}x->>'order_id'
 {% elif var('release_source')=='ebay_sim' %}x->>'orderId'
 {% else %}x->>'receipt_id'{% endif %} AS order_id
 FROM candidates r
 {% if var('release_source')=='ebay_sim' %}
 LEFT JOIN raw.raw_records parent ON parent.raw_record_id=(r.metadata->>'order_raw_id')::UUID
 {% endif %}
 LEFT JOIN LATERAL jsonb_array_elements(
 {% if var('release_source')=='internal_web' %}r.parsed_payload->'orders'
 {% elif var('release_source')=='ebay_sim' %}
 CASE WHEN r.resource_type='ebay_orders' THEN r.parsed_payload->'orders'
      WHEN r.resource_type='ebay_order' THEN jsonb_build_array(r.parsed_payload)
      ELSE jsonb_build_array(jsonb_build_object('orderId',coalesce(r.metadata->>'order_id',parent.parsed_payload->>'orderId'))) END
 {% else %}jsonb_build_array(r.parsed_payload){% endif %}) x ON TRUE
)
INSERT INTO ops.delta_raw_keys(raw_record_id,source_system,source_account_id,source_order_id)
SELECT raw_record_id,source_system,source_account_id,
       CASE WHEN x IS NULL THEN NULL ELSE coalesce(nullif(order_id,''),'') END
FROM routed GROUP BY 1,2,3,4 ON CONFLICT DO NOTHING;
{% endmacro %}

{% macro export_delta_hooks() %}
{% set hooks={'route':delta_route_sql(),
 'functions':create_canonical_jsonb_function() ~ create_ebay_canonical_function() ~ create_etsy_functions(),
 'prepare':populate_etsy_cache() if var('release_source')=='etsy_sim' else 'SELECT 1',
 'finish':record_etsy_mapping_exceptions() if var('release_source')=='etsy_sim' else 'SELECT 1'} %}
{{ log('DELTA_HOOKS_JSON=' ~ tojson(hooks),info=true) }}
{% endmacro %}
