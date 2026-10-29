"""Independent opt-in inbox drain and missed-notification recovery schedules."""
from datetime import timedelta
import os
import subprocess

import pendulum
from airflow.sdk import dag, task, get_current_context, Param
from airflow.sdk.exceptions import AirflowFailException
from orchestration.scheduling import periodic_schedule


def invoke(mode, abort=False):
    ctx = get_current_context()
    command = ['/opt/airflow/project-venv/bin/python', '-m', 'orchestration.polling',
               '--source', 'etsy_sim', '--collection-mode', mode,
               '--wait-seconds','15',
               '--reuse-cycle-config',
               '--execution-id', ctx['run_id'] + ':' + mode, '--dag-id', ctx['dag'].dag_id,
               '--airflow-run-id', ctx['run_id']]
    if mode == 'recovery':
        command += ['--window-end', ctx['data_interval_end'].isoformat(),
                    '--overlap-seconds', os.environ.get('POLL_OVERLAP_SECONDS', '120'),
                    '--checkpoint-stream',os.environ.get('ETSY_RECOVERY_STREAM','receipts_polling')]
        initial = os.environ.get('ETSY_RECOVERY_INITIAL_START', '')
        if initial:
            command += ['--initial-start', initial]
    if abort:
        command += ['--abort']
    if ctx['params']['inject_test_failure']:
        command += ['--inject-test-failure']
    for name in ('fault_after_raw_once','fault_after_freeze_once'):
        if ctx['params'][name]:
            command += ['--'+name.replace('_','-')]
    result = subprocess.run(command, check=False)
    if result.returncode == 42:
        raise AirflowFailException('Durable Etsy stage budget exhausted')
    result.check_returncode()


def make_dag(mode, manual=False):
    interval = int(os.environ.get('ETSY_' + ('INBOX' if mode=='drain' else 'RECOVERY') + '_INTERVAL_SECONDS', '300'))
    if interval < 10:
        raise ValueError('Etsy interval must be at least 10 seconds')
    @dag(dag_id='etsy_replay' if manual else 'etsy_inbox' if mode=='drain' else 'etsy_recovery',
         schedule=periodic_schedule(timedelta(seconds=interval), manual), start_date=pendulum.datetime(2026,10,17,tz='UTC'),
         catchup=False, is_paused_upon_creation=True, max_active_runs=1, max_active_tasks=1,
         dagrun_timeout=timedelta(minutes=30),
         default_args={'retries':4,'retry_delay':timedelta(seconds=30),'execution_timeout':timedelta(minutes=15)},
         params={name:Param(False,type='boolean') for name in ('inject_test_failure','fault_after_raw_once','fault_after_freeze_once')}, tags=['m06','etsy',mode])
    def pipeline():
        @task
        def cycle():
            invoke(mode)
        @task(trigger_rule='one_failed',retries=0)
        def failed_workflow():
            invoke(mode,abort=True)
            raise AirflowFailException('Etsy workflow failed; audit retained')
        cycle() >> failed_workflow()
    return pipeline()


etsy_inbox = make_dag('drain')
etsy_recovery = make_dag('recovery')
etsy_replay = make_dag('drain',manual=True)
