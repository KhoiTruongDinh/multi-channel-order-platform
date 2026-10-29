{% macro create_etsy_functions() %}
CREATE OR REPLACE FUNCTION build.etsy_canonical_json(input_json JSONB)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE STRICT AS $function$
DECLARE result JSONB := input_json; alias_name TEXT; main_name TEXT;
BEGIN
    FOREACH alias_name IN ARRAY ARRAY['create_timestamp','update_timestamp'] LOOP
        main_name := CASE alias_name WHEN 'create_timestamp' THEN 'created_timestamp' ELSE 'updated_timestamp' END;
        IF result ? alias_name THEN
            IF result ? main_name AND result->alias_name IS DISTINCT FROM result->main_name THEN
                RAISE EXCEPTION 'Conflicting Etsy timestamp alias';
            END IF;
            result := (result-alias_name) || jsonb_build_object(main_name,result->alias_name);
        END IF;
    END LOOP;
    RETURN build.ebay_canonical_json(result);
END;
$function$;
CREATE OR REPLACE FUNCTION build.etsy_money(value JSONB)
RETURNS NUMERIC LANGUAGE plpgsql IMMUTABLE STRICT AS $function$
BEGIN
    IF value='null'::JSONB THEN RETURN NULL; END IF;
    IF jsonb_typeof(value->'amount') IS DISTINCT FROM 'number'
       OR jsonb_typeof(value->'divisor') IS DISTINCT FROM 'number'
       OR (value->>'amount') !~ '^-?[0-9]+$'
       OR (value->>'divisor') !~ '^[0-9]+$'
       OR (value->>'divisor')::NUMERIC<=0
       OR coalesce(value->>'currency_code','') !~ '^[A-Z]{3}$' THEN
        RAISE EXCEPTION 'Invalid Etsy Money: complete object and positive divisor required';
    END IF;
    RETURN (value->>'amount')::NUMERIC/(value->>'divisor')::NUMERIC;
END;
$function$;
{% endmacro %}

{% macro record_etsy_mapping_exceptions() %}
INSERT INTO ops.data_exceptions
    (exception_id,exception_key,rule_id,severity,state,source_system,source_account_id,
     source_entity_id,batch_id,processing_version,reason,details,first_seen_at,last_seen_at)
SELECT md5(concat_ws(':','etsy:map',snapshot_id::TEXT,source_line_id,'{{ var("mapping_version") }}'))::UUID,
       concat_ws(':','etsy:map',snapshot_id::TEXT,source_line_id,'{{ var("mapping_version") }}'),
       'ETSY_PRODUCT_MAPPING','WARNING','OPEN','etsy_sim','7001',source_line_id,
       '{{ var("batch_id") }}'::UUID,'{{ var("transformation_version") }}',
       'Unresolved source product; line retained without invented canonical identity',
       jsonb_build_object('snapshot_id',snapshot_id,'mapping_status',mapping_status),now(),now()
  FROM {{ ref('etsy_candidate_order_line_snapshot_history') }} WHERE mapping_status<>'CONFIRMED'
ON CONFLICT (exception_key) DO UPDATE SET last_seen_at=EXCLUDED.last_seen_at;
{% endmacro %}
