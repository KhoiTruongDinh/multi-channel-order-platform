"""Opt-in current-clock polling. No source fixtures, SQL transformations or IO at parse."""
from datetime import timedelta
import os
import subprocess

import pendulum
from airflow.sdk import dag,task,get_current_context,Param
from airflow.sdk.exceptions import AirflowFailException


def invoke(source, abort=False):
    c=get_current_context()
    prefix='WEBSITE' if source=='internal_web' else 'EBAY'
    command=['/opt/airflow/project-venv/bin/python','-m','orchestration.polling',
        '--source',source,'--execution-id',c['run_id'],'--dag-id',c['dag'].dag_id,
        '--window-end',c['data_interval_end'].isoformat(),
        '--overlap-seconds',os.environ.get('POLL_OVERLAP_SECONDS','120')]
    initial=os.environ.get(prefix+'_POLL_INITIAL_START','')
    if initial:
        command+=['--initial-start',initial]
    if abort:
        command+=['--abort']
    for flag in ('fault_after_raw_once','fault_after_freeze_once','inject_test_failure'):
        if c['params'][flag]:
            command+=['--'+flag.replace('_','-')]
    result=subprocess.run(command,check=False)
    if result.returncode==42:
        raise AirflowFailException('Durable polling stage budget exhausted')
    result.check_returncode()


def build_dag(source,prefix,manual=False):
    interval=int(os.environ.get(prefix+'_POLL_INTERVAL_SECONDS','300'))
    if interval<10:
        raise ValueError(prefix+' polling interval must be at least 10 seconds')
    name='website_polling' if source=='internal_web' else 'ebay_polling'
    @dag(dag_id=name+('_replay' if manual else ''),
         schedule=None if manual else timedelta(seconds=interval),catchup=False,
         start_date=pendulum.datetime(2026,10,17,tz='UTC'),
         is_paused_upon_creation=True,max_active_runs=1,max_active_tasks=1,
         dagrun_timeout=timedelta(minutes=30),
         default_args={'retries':4,'retry_delay':timedelta(seconds=30),'execution_timeout':timedelta(minutes=15)},
         params={flag:Param(False,type='boolean') for flag in
                 ('fault_after_raw_once','fault_after_freeze_once','inject_test_failure')},
         tags=['m05b','polling',source])
    def pipeline():
        @task
        def cycle():
            invoke(source)
        @task(trigger_rule='one_failed',retries=0)
        def failed_workflow():
            invoke(source,abort=True)
            raise AirflowFailException('Polling workflow failed; audit retained')
        cycle() >> failed_workflow()
    return pipeline()


website_polling=build_dag('internal_web','WEBSITE')
ebay_polling=build_dag('ebay_sim','EBAY')
ebay_polling_replay=build_dag('ebay_sim','EBAY',manual=True)
