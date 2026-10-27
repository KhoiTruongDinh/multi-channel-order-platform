"""Bounded website acquisition and tested release; business logic stays in CLI/dbt."""
from datetime import timedelta
import subprocess

import pendulum
from airflow.sdk import dag, task, get_current_context, Param
from airflow.exceptions import AirflowFailException


def invoke(stage):
    context = get_current_context()
    params = context['params']
    command = [
        '/opt/airflow/project-venv/bin/python', '-m', 'orchestration.website_workflow',
        '--stage', stage, '--execution-id', context['run_id'],
        '--dag-id', 'website_orders',
        '--window-start', params['window_start'], '--window-end', params['window_end'],
        '--observed-at', params['observed_at'],
    ]
    for name in ('fault_after_raw_once', 'fault_after_freeze_once', 'inject_test_failure'):
        if params[name]:
            command.append('--' + name.replace('_', '-'))
    result = subprocess.run(command, check=False)
    if result.returncode == 42:
        raise AirflowFailException('Durable attempt budget exhausted; explicit new replay cycle required')
    result.check_returncode()


@dag(
    dag_id='website_orders', schedule=None, catchup=False,
    start_date=pendulum.datetime(2026, 10, 17, tz='UTC'),
    max_active_runs=1, max_active_tasks=1,
    dagrun_timeout=timedelta(minutes=20),
    default_args={'retries': 4, 'retry_delay': timedelta(seconds=30),
                  'execution_timeout': timedelta(minutes=5)},
    params={
        'window_start': Param('2026-10-17T09:09:00Z', type='string', format='date-time'),
        'window_end': Param('2026-10-17T09:15:00Z', type='string', format='date-time'),
        'observed_at': Param('2026-10-17T09:15:00Z', type='string', format='date-time'),
        'fault_after_raw_once': Param(False, type='boolean'),
        'fault_after_freeze_once': Param(False, type='boolean'),
        'inject_test_failure': Param(False, type='boolean'),
    }, tags=['m04', 'website', 's01'],
)
def website_orders():
    @task
    def collect():
        invoke('collect')

    @task
    def freeze():
        invoke('freeze')

    @task
    def build_and_test():
        invoke('build_and_test')

    @task
    def publish():
        invoke('publish')

    @task(trigger_rule='one_failed', retries=0)
    def failed_workflow():
        invoke('abort')
        # A failing leaf preserves the failed DAG outcome after audit cleanup.
        raise AirflowFailException('Website workflow failed; inspect durable attempts and batch audit')

    acquired = collect()
    frozen = freeze()
    built = build_and_test()
    released = publish()
    acquired >> frozen >> built >> released
    [acquired, frozen, built, released] >> failed_workflow()


website_orders()
