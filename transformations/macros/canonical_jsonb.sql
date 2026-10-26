{% macro create_canonical_jsonb_function() %}
CREATE OR REPLACE FUNCTION build.canonical_jsonb_text(input_json JSONB)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $function$
DECLARE
    result TEXT;
BEGIN
    CASE jsonb_typeof(input_json)
        WHEN 'object' THEN
            SELECT '{' || COALESCE(string_agg(to_jsonb(entry.key)::TEXT || ':' || build.canonical_jsonb_text(entry.value), ',' ORDER BY entry.key COLLATE "C"), '') || '}'
              INTO result
              FROM jsonb_each(input_json) AS entry(key, value);
        WHEN 'array' THEN
            SELECT '[' || COALESCE(string_agg(build.canonical_jsonb_text(element.value), ',' ORDER BY element.ordinality), '') || ']'
              INTO result
              FROM jsonb_array_elements(input_json) WITH ORDINALITY AS element(value, ordinality);
        ELSE
            result := input_json::TEXT;
    END CASE;
    RETURN result;
END;
$function$;
{% endmacro %}
