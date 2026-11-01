{% macro mapping_release_versions() -%}
{# A declared composite release for retained S01 plus append-only S02 data. #}
{% if var('mapping_version') == 'local-live-v1' %}
('s01-v1', 's02-catalog-v1')
{% else %}
('{{ var("mapping_version") | replace("'", "''") }}')
{% endif %}
{%- endmacro %}
