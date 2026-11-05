"""Installed ONLY by the disposable M08C controller; never in normal DAG image."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import time

import pendulum
from airflow.sdk import dag, task, get_current_context, Param
from airflow.sdk.exceptions import AirflowFailException


def invoke(abort=False):
    context = get_current_context()
    command = ['/opt/airflow/project-venv/bin/python', '-m', 'orchestration.polling',
        '--source', 'internal_web', '--execution-id', context['run_id'],
        '--dag-id', 'm08c_recovery', '--mapping-version', 's01-v1',
        '--window-end', context['data_interval_end'].isoformat(),
        '--initial-start', '2026-10-17T00:00:00Z', '--wait-seconds', '300']
    if abort:
        command += ['--abort', '--reuse-cycle-config']
    for key in ('fault_after_raw_once', 'fault_after_freeze_once', 'inject_test_failure'):
        if context['params'][key]:
            command += ['--' + key.replace('_', '-')]
    result = subprocess.run(command, check=False)
    if result.returncode == 42:
        raise AirflowFailException('Durable budget exhausted; task clear is not budget reset')
    result.check_returncode()


@dag(dag_id='m08c_recovery',
     schedule=None if any(Path('/opt/airflow/state/' + name).is_file()
                          for name in ('m08c-drain', 'polling-drain')) else timedelta(seconds=30),
     start_date=pendulum.datetime(2026, 10, 17, tz='UTC'), catchup=False,
     is_paused_upon_creation=True, max_active_runs=1, max_active_tasks=1,
     dagrun_timeout=timedelta(minutes=25),
     default_args={'retries': 4, 'retry_delay': timedelta(seconds=10)},
     params={name: Param(False, type='boolean') for name in
             ('fault_after_raw_once', 'fault_after_freeze_once', 'inject_test_failure', 'barrier', 'exhaust_stage')},
     tags=['disposable-only', 'm08c'])
def recovery():
    @task
    def cycle():
        context = get_current_context()
        if context['params']['barrier']:
            Path('/opt/airflow/state/m08c-ready').touch()
            deadline = time.monotonic() + 180
            while not Path('/opt/airflow/state/m08c-release').exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError('M08C controller barrier timeout')
                time.sleep(.2)
        if context['params']['exhaust_stage']:
            from argparse import Namespace
            from unittest.mock import patch
            from orchestration import polling, website_workflow as workflow
            args = Namespace(source='internal_web', execution_id=context['run_id'], dag_id='m08c_recovery',
                airflow_run_id=context['run_id'], collection_mode='recovery', checkpoint_stream=None,
                reuse_cycle_config=False, window_end=context['data_interval_end'],
                initial_start=datetime(2026,10,17,tzinfo=timezone.utc), overlap_seconds=120,
                mapping_version='s01-v1', transformation_version='m05b-v1',
                fault_after_raw_once=False, fault_after_freeze_once=False, inject_test_failure=False)
            polling.prepare(args)
            try:
                with patch.object(workflow, 'perform', side_effect=RuntimeError('M08C declared permanent stage fault')):
                    workflow.run_stage(args, 'collect')
            except workflow.AttemptBudgetExhausted as error:
                raise AirflowFailException(str(error)) from error
            return
        invoke()

    @task(trigger_rule='one_failed', retries=0)
    def failed_workflow():
        invoke(abort=True)
        raise AirflowFailException('Failed recovery audit retained')

    cycle() >> failed_workflow()


recovery()
