{% macro create_ebay_canonical_function() %}
CREATE OR REPLACE FUNCTION build.ebay_canonical_json(input_json JSONB)
RETURNS JSONB LANGUAGE plpgsql IMMUTABLE STRICT AS $function$
DECLARE result JSONB; entry RECORD; child JSONB; identity_key TEXT;
BEGIN
    IF jsonb_typeof(input_json) = 'object' THEN
        result := '{}'::JSONB;
        FOR entry IN SELECT * FROM jsonb_each(input_json) LOOP
            child := build.ebay_canonical_json(entry.value);
            identity_key := CASE entry.key WHEN 'lineItems' THEN 'lineItemId'
                WHEN 'fulfillments' THEN 'fulfillmentId' WHEN 'transactions' THEN 'transaction_id' END;
            IF identity_key IS NOT NULL AND jsonb_typeof(child) = 'array' THEN
                IF EXISTS (SELECT 1 FROM jsonb_array_elements(child) x WHERE NOT x ? identity_key)
                   OR (SELECT count(*) FROM jsonb_array_elements(child)) <>
                      (SELECT count(DISTINCT x->>identity_key) FROM jsonb_array_elements(child) x) THEN
                    RAISE EXCEPTION 'Missing or duplicate collection identity';
                END IF;
                SELECT coalesce(jsonb_agg(x ORDER BY x->>identity_key COLLATE "C"),'[]'::JSONB)
                  INTO child FROM jsonb_array_elements(child) x;
            END IF;
            result := result || jsonb_build_object(entry.key,child);
        END LOOP;
        RETURN result;
    ELSIF jsonb_typeof(input_json) = 'array' THEN
        SELECT coalesce(jsonb_agg(build.ebay_canonical_json(x) ORDER BY n),'[]'::JSONB)
          INTO result FROM jsonb_array_elements(input_json) WITH ORDINALITY t(x,n);
        RETURN result;
    END IF;
    RETURN input_json;
END;
$function$;
{% endmacro %}
