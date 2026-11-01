"""Fresh isolated empty-source scheduler/drain regression, NOT full S02 acceptance."""
import argparse
import json
import sys

from test_support import m08a as isolation
from test_support.m08b import Campaign, DAGS, rows, snapshot


def probe(h):
    campaign=Campaign(h,17,'drain-probe')
    h.report['harness_hashes']['test_support/m08b_drain_probe.py']=isolation.digest(isolation.ROOT/'test_support/m08b_drain_probe.py')
    try:
        h.dc(['up','--detach','--wait','--wait-timeout','180','ebay-sim','etsy-sim','etsy-receiver'])
        h.dc(['up','--detach','--wait','--wait-timeout','420','airflow'],timeout=450)
        errors=h.dc(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json'])
        isolation.require(json.loads(errors)==[],'DAG import errors')
        campaign.wait(lambda:len(rows(h,'SELECT dag_id FROM dag','airflow_meta'))==7,'drain-probe DAG discovery')
        campaign.dag('unpause',DAGS)
        def two():
            runs=campaign.scheduled()
            isolation.require(not any(r['state']=='failed' for r in runs),'Failed probe scheduled run')
            return all(sum(r['dag_id']==d and r['state']=='success' for r in runs)>=2 for d in DAGS)
        campaign.wait(two,'drain-probe two successes per path')
        def active():
            running=rows(h,"SELECT dag_id,run_id,state FROM dag_run WHERE state IN ('queued','running')",'airflow_meta')
            campaign.result['inflight_before_drain']=running
            return bool(running)
        campaign.wait(active,'drain-probe real in-flight runs')
        campaign.finish_schedules()
        isolation.require(not snapshot(h)['orders'],'Empty-source drain probe created business orders')
        for test in ('test_m05_http.py','test_m06_unit.py'):
            h.run('airflow',f'/repo/tests/{test}',reads=True,entrypoint='/opt/airflow/project-venv/bin/python')
        h.run('airflow','-c',"import os; assert all(not os.path.exists('/repo/'+p) for p in ('runtime','.env','.git')); print('S02 narrow test-mount boundary PASS')",
              reads=True,entrypoint='/opt/airflow/project-venv/bin/python')
        campaign.result.update(status='PASS',operations_committed=0,final_orders=0,
            finished_at=isolation.utc(),purpose='maintenance/empty-window regression; not S02 generator proof')
        print('M08B auxiliary drain/empty-source/narrow-mount regression PASS',flush=True)
    finally:
        if campaign.result['status']=='RUNNING':
            campaign.result.update(status='FAIL',finished_at=isolation.utc())
        campaign.ledger.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True)
    a=p.parse_args()
    h=isolation.Harness(a.id)
    isolation.require(h.marker.get('profile')=='m08b' and h.marker.get('drain_signal'), 'Fresh drain-capable B ID required')
    isolation.accept(h,baseline_fn=probe)


if __name__=='__main__':
    try:
        main()
    except isolation.SafetyError as error:
        print('M08B drain regression failed: '+str(error),file=sys.stderr)
        sys.exit(1)
