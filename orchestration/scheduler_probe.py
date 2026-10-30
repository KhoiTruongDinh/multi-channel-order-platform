"""Small metadata sampler outside DAGs; exports no credentials or free-form text."""
import argparse
from datetime import datetime,timezone
import os
import time
import psycopg
from orchestration.website_workflow import connect
from transformation.source_config import SOURCES

DAGS={'website_orders':'internal_web','website_polling':'internal_web',
      'ebay_polling':'ebay_sim','ebay_polling_replay':'ebay_sim',
      'etsy_inbox':'etsy_sim','etsy_recovery':'etsy_sim','etsy_replay':'etsy_sim'}


def sample():
    with psycopg.connect(host=os.environ.get('PLATFORM_DB_HOST','postgres'),dbname='airflow_meta',
                         user='airflow_app',password=os.environ['AIRFLOW_APP_PASSWORD'],
                         connect_timeout=5,options='-c statement_timeout=10000') as meta:
        heartbeat=meta.execute("SELECT max(latest_heartbeat) FROM job WHERE job_type='SchedulerJob' AND state='running'").fetchone()[0]
        rows=meta.execute("""SELECT d.dag_id,d.is_paused,(SELECT r.state FROM dag_run r
            WHERE r.dag_id=d.dag_id ORDER BY r.queued_at DESC NULLS LAST LIMIT 1)
            FROM dag d WHERE d.dag_id=ANY(%s)""",(list(DAGS),)).fetchall()
    at=datetime.now(timezone.utc)
    with connect() as target:
        for dag,paused,state in rows:
            source=DAGS[dag]
            target.execute("""INSERT INTO ops.scheduler_observations(dag_id,source_system,source_account_id,
                is_paused,latest_run_state,scheduler_heartbeat_at,observed_at) VALUES(%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(dag_id) DO UPDATE SET is_paused=EXCLUDED.is_paused,
                latest_run_state=EXCLUDED.latest_run_state,scheduler_heartbeat_at=EXCLUDED.scheduler_heartbeat_at,
                observed_at=EXCLUDED.observed_at""",(dag,source,SOURCES[source][0],paused,state,heartbeat,at))
    print(f'scheduler observations={len(rows)} at={at.isoformat()}',flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--once',action='store_true')
    args=p.parse_args()
    while True:
        try:
            sample()
        except Exception as error:
            print(f'observer unavailable: {type(error).__name__}',flush=True)
            if args.once:
                raise
        if args.once:
            return
        time.sleep(30)


if __name__=='__main__':
    main()
