"""Acceptance maintenance: close platform parents after terminal Airflow failure.

DAG timeout can skip the failure watcher. Never clear task/budget evidence or
abort a still-running DAG; delegate to the existing guarded workflow abort.
"""
import os
import subprocess
import sys

import psycopg
from ingestion.etsy_common import connect
from orchestration.website_workflow import identity

DAGS = ('etsy_inbox', 'etsy_recovery', 'etsy_replay', 'website_polling', 'ebay_polling')


def abort_command(row):
    run_id, source, dag_id, airflow_run_id, log_reference, window_end = row
    scope = {'website_polling': 'internal_web', 'ebay_polling': 'ebay_sim',
             'etsy_inbox': 'etsy_sim', 'etsy_recovery': 'etsy_sim', 'etsy_replay': 'etsy_sim'}
    prefix = f'm04:poll:{source}:'
    if scope.get(dag_id) != source or not log_reference.startswith(prefix):
        raise ValueError('unrecognized drain workflow identity')
    execution = log_reference[len(prefix):]
    if identity(f'poll:{source}:{execution}', 'workflow') != run_id:
        raise ValueError('drain workflow identity mismatch')
    command = [sys.executable, '-m', 'orchestration.polling', '--source', source,
               '--execution-id', execution, '--dag-id', dag_id,
               '--airflow-run-id', airflow_run_id, '--reuse-cycle-config',
               '--abort', '--wait-seconds', '15']
    if window_end is not None:
        command += ['--window-end', window_end.isoformat()]
    return command


def main():
    with connect() as c:
        parents = c.execute("""SELECT run_id,source_system,airflow_dag_id,
            airflow_run_id,log_reference,requested_window_end
            FROM ops.pipeline_runs WHERE stage='RECOVER' AND status='RUNNING'
            AND airflow_dag_id=ANY(%s)""", (list(DAGS),)).fetchall()
    with psycopg.connect(host='postgres', dbname='airflow_meta', user='airflow_app',
                         password=os.environ['AIRFLOW_APP_PASSWORD']) as meta:
        for row in parents:
            state = meta.execute('SELECT state FROM dag_run WHERE dag_id=%s AND run_id=%s', row[2:4]).fetchone()
            if state != ('failed',):
                continue
            live = meta.execute("""SELECT 1 FROM task_instance WHERE dag_id=%s AND run_id=%s
                AND state IN ('running','queued','restarting') LIMIT 1""", row[2:4]).fetchone()
            if live:
                continue
            subprocess.run(abort_command(row), check=True)
            with connect() as c:
                status = c.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s', (row[0],)).fetchone()
            if status != ('FAILED',):
                raise RuntimeError(f'terminal DAG parent not closed: {row[0]}')
            print(f'M06 drain closed FAILED Airflow parent {row[2]} {row[3]} (evidence retained)')


if __name__ == '__main__':
    main()
