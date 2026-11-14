{% macro etsy_cache_version() -%}
{{ return(local_md5(create_etsy_functions() ~ create_ebay_canonical_function() ~ create_canonical_jsonb_function())) }}
{%- endmacro %}

{% macro etsy_cache_inputs() %}
SELECT r.raw_record_id, r.run_id, r.source_system, r.source_account_id, r.acquired_at, r.byte_sha256, r.parsed_payload
  FROM {{ source('acquisition','raw_records') }} r
  INNER JOIN {{ source('operations','batch_inputs') }} i USING(raw_record_id)
 WHERE i.batch_id={{ batch_uuid() }} AND r.source_system='etsy_sim'
   AND r.source_account_id='7001' AND r.resource_type='etsy_receipt' AND r.response_status=200
{% endmacro %}

{% macro populate_etsy_cache() %}
INSERT INTO {{ source('canonical_cache','etsy_payloads') }}
    (source_system,source_account_id,byte_sha256,normalization_version,
     source_payload,order_json,content_fingerprint)
WITH missing AS MATERIALIZED (
    SELECT r.source_system,r.source_account_id,r.byte_sha256,r.parsed_payload
      FROM ({{ etsy_cache_inputs() }}) r
      LEFT JOIN {{ source('canonical_cache','etsy_payloads') }} c
        ON (c.source_system,c.source_account_id,c.byte_sha256,c.normalization_version)=
           (r.source_system,r.source_account_id,r.byte_sha256,'{{ etsy_cache_version() }}')
     WHERE c.byte_sha256 IS NULL
     GROUP BY r.source_system,r.source_account_id,r.byte_sha256,r.parsed_payload
), normalized AS MATERIALIZED (
    SELECT m.source_system,m.source_account_id,m.byte_sha256,m.parsed_payload,
           build.etsy_canonical_json(parsed_payload) AS order_json FROM missing m
)
SELECT source_system,source_account_id,byte_sha256,'{{ etsy_cache_version() }}',
       parsed_payload,order_json,
       sha256(convert_to(build.canonical_jsonb_text(order_json),'UTF8'))
  FROM normalized
ON CONFLICT DO NOTHING;
-- Same scoped bytes must decode identically. Never silently reuse a hash collision
-- or a stale parsed representation; roll back this model's cache inserts on error.
DO $cache_guard$
BEGIN
    IF EXISTS (
        SELECT 1 FROM ({{ etsy_cache_inputs() }}) r
        INNER JOIN {{ source('canonical_cache','etsy_payloads') }} c
          ON (c.source_system,c.source_account_id,c.byte_sha256,c.normalization_version)=
             (r.source_system,r.source_account_id,r.byte_sha256,'{{ etsy_cache_version() }}')
        WHERE c.source_payload::TEXT IS DISTINCT FROM r.parsed_payload::TEXT
    ) THEN
        RAISE EXCEPTION 'Etsy canonical cache payload identity mismatch';
    END IF;
END;
$cache_guard$;
{% endmacro %}
