{% if var('inject_test_failure', false) %}
SELECT 'intentional M03 test failure' AS failure
{% else %}
SELECT 1 AS failure WHERE FALSE
{% endif %}
