{% if var('delta_mode', false) %}
SELECT 'intentional delta gate failure' AS failure
 WHERE current_setting('platform.inject_test_failure')='true'
{% elif var('inject_test_failure', false) %}
SELECT 'intentional M03 test failure' AS failure
{% else %}
SELECT 1 AS failure WHERE FALSE
{% endif %}
