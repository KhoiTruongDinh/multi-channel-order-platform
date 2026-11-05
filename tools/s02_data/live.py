"""One-time local live service startup; no dataset selection or data reset."""
import json
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from tools.s02_data.load import ROOT,migrations,query
from test_support.s02_plan import literal

DAGS=('website_polling','ebay_polling','etsy_inbox','etsy_recovery')


@contextmanager
def startup_lock():
    """OS lock survives neither crash nor exit; the empty lock file is harmless."""
    path=ROOT/'runtime'/'live-up.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a+b') as handle:
        if path.stat().st_size==0: handle.write(b' '); handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('another live-up is running; wait for its result') from None
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)


def require_live(db):
    for service in ('ebay-sim','etsy-sim'):
        mode=db.command(['exec','-T',service,'python','-c',
            'import os; print(os.environ.get("SIMULATOR_MODE",""))'])
        if mode!='live-pg': raise ValueError('run live-up before generate; sources are not live-pg')
    pipeline=db.command(['exec','-T','airflow','python','-c',
        'import os; print("live-pg" if os.environ.get("S02_LOCAL_PLAYBACK")!="true" and os.environ.get("POLLING_LIVE_CURRENT_TIME")=="true" and os.environ.get("POLLING_MAPPING_VERSION")=="local-live-v1" else "misconfigured")'])
    if pipeline!='live-pg': raise ValueError('run live-up; Airflow is not configured for live sources')
    ready=compose(db,['ps','--format','json','live-source'])
    state=json.loads(ready) if ready.strip() else {}
    if state.get('State')!='running' or state.get('Health')!='healthy':
        raise ValueError('live-source worker is not healthy; inspect logs before claiming readiness')


def require_live_storage(db):
    """Producers must not depend on Airflow uptime or DAG pause state."""
    ready=query(db,"SELECT to_regclass('s02.live_batches') AS relation_name")
    if not ready[0]['relation_name']: raise ValueError('run live-up once before live generation')
    for service in ('ebay-sim','etsy-sim'):
        try:
            mode=db.command(['exec','-T',service,'python','-c',
                'import os; print(os.environ.get("SIMULATOR_MODE",""))'])
        except RuntimeError:
            print('Source service unavailable: '+service+'; admission can continue, visibility waits for service recovery',flush=True)
            continue
        if mode!='live-pg': raise ValueError('run live-up; '+service+' is still fixture/replay mode')


def drain(db,timeout=600):
    """Keep retries runnable; pause only after that DAG has no active runs."""
    return _drain_schedules(db, timeout, DAGS)


def _drain_schedules(db, timeout, dags):
    """Shared algorithm; disposable controllers supply only their test DAG IDs."""
    deadline=time.monotonic()+timeout
    states={r['dag_id']:r.get('is_paused',True) for r in query(db,'SELECT dag_id,is_paused FROM dag','airflow_meta')}
    known=set(states)
    active=query(db,"SELECT DISTINCT dag_id FROM dag_run WHERE state IN ('running','queued')",'airflow_meta')
    active_ids={r['dag_id'] for r in active}
    if active_ids-set(dags):
        raise ValueError('manual/replay DAG active; finish it before live-up')
    # Upgrade the small parse-time helper in older running images as a one-time
    # deployment step, without restarting active workers or altering run state.
    db.command(['cp',str(ROOT/'orchestration/scheduling.py'),
                'airflow:/opt/project/orchestration/scheduling.py'])
    db.command(['exec','-T','airflow','python','-c',
                'from pathlib import Path; Path("/opt/airflow/state/polling-drain").touch()'])
    paused=set()
    for dag in dags:
        if dag not in known: continue
        action='unpause' if dag in active_ids else 'pause'
        if states[dag] != (action=='pause'):
            db.command(['exec','-T','airflow','airflow','dags',action,dag])
        if action=='pause': paused.add(dag)
    while True:
        active={r['dag_id'] for r in query(db,"SELECT DISTINCT dag_id FROM dag_run WHERE state IN ('running','queued')",'airflow_meta')}
        if active-set(dags): raise ValueError('manual/replay DAG became active during drain')
        # A run may have been created between the idle read and pause command.
        # Let that run finish too, rather than stranding it behind the pause flag.
        for dag in active&paused:
            db.command(['exec','-T','airflow','airflow','dags','unpause',dag]); paused.remove(dag)
        for dag in set(dags)&known-paused-active:
            db.command(['exec','-T','airflow','airflow','dags','pause',dag]); paused.add(dag)
        if not active and set(dags)&known<=paused: return
        if time.monotonic()>deadline:
            raise RuntimeError('Drain timeout; no source switch. Active DAGs remain runnable for retries; inspect before retrying')
        time.sleep(2)


def compose(db,args,timeout=600):
    command=db.base+['--file',str(ROOT/'infra/compose.live.yaml'),'--profile','*']+args
    result=subprocess.run(command,capture_output=True,text=True,timeout=timeout,cwd=ROOT)
    if result.returncode: raise RuntimeError('Live Compose command failed; inspect service logs (secrets suppressed)')
    return result.stdout


def probe_sources(model):
    """Health means the authenticated DB-backed source interface really works."""
    now=datetime.now(timezone.utc)
    for kind in ('ebay','etsy'):
        service=model['services'][kind+'-sim']
        port=next(p['published'] for p in service['ports'] if p['target']==80)
        if kind=='ebay':
            path='/sell/fulfillment/v1/order?'+urlencode(dict(
                filter='lastmodifieddate:[2026-01-08T00:00:00Z..'+now.isoformat()+']',limit=1,offset=0))
        else:
            path='/v3/application/shops/7001/receipts?'+urlencode(dict(min_last_modified=1767830400,
                max_last_modified=int(now.timestamp()),limit=1,offset=0,sort_on='updated',sort_order='asc'))
        try:
            token=service['environment'][kind.upper()+'_SIM_TOKEN']
            with urlopen(Request(f'http://127.0.0.1:{port}'+path,headers={'Authorization':'Bearer '+token}),timeout=15) as response:
                value=json.load(response)
            if not isinstance(value.get('orders' if kind=='ebay' else 'results'),list):
                raise ValueError('unexpected source response')
        except Exception:
            raise RuntimeError(kind+' live source read failed; inspect SIM/DB role before generating') from None


def up(db):
    print('Live startup: validating configuration',flush=True)
    model=json.loads(compose(db,['config','--format','json']))
    # Validate credentials and prerequisites before pausing any schedules.
    passwords={kind:model['services'][kind+'-sim']['environment']['S02_DB_PASSWORD'] for kind in ('ebay','etsy')}
    if any(not p for p in passwords.values()): raise ValueError('set stable S02 reader passwords in .env')
    for name,sql in [('website_source',"SELECT to_regclass('public.orders') AS relation_name"),
                     ('data_platform',"SELECT to_regclass('ops.polling_cycles') AS relation_name")]:
        if not query(db,sql,name)[0]['relation_name']: raise ValueError('run existing M01-M07 migrations first')
    print('Live startup: draining existing runs without resetting retries',flush=True)
    drain(db)
    migrations(db)
    db.sql((ROOT/'migrations/marketplace_sim/003_live_batches.sql').read_text())
    for kind,password in passwords.items():
        db.sql('ALTER ROLE s02_'+kind+'_reader PASSWORD '+literal(password)+';')
    print('Live startup: building/starting SIMs, source worker, Airflow and reports',flush=True)
    compose(db,['up','--detach','--build','--wait','--wait-timeout','420',
        'postgres','ebay-sim','etsy-sim','etsy-receiver','live-source','airflow','report','scheduler-observer'],timeout=900)
    errors=json.loads(db.command(['exec','-T','airflow','airflow','dags','list-import-errors','--output','json']))
    if errors: raise RuntimeError('Airflow import errors; polling remains paused')
    probe_sources(model)
    deadline=time.monotonic()+120
    while not set(DAGS)<=set(r['dag_id'] for r in query(db,'SELECT dag_id FROM dag','airflow_meta')):
        if time.monotonic()>deadline: raise RuntimeError('Live DAG discovery timeout')
        time.sleep(5)
    print('Live startup: services healthy, restoring four periodic schedules',flush=True)
    db.command(['exec','-T','airflow','python','-c',
        'from pathlib import Path; Path("/opt/airflow/state/polling-drain").unlink(missing_ok=True)'])
    for dag in DAGS: db.command(['exec','-T','airflow','airflow','dags','unpause',dag])
    return dict(status='LIVE_SERVICES_READY',periodic_dags=list(DAGS),
        source_mode='live-pg',pipeline_clock='actual UTC',data='retained; no reset',
        next='python -m tools.s02_data generate --config tools/s02_data/config/observe_6min.json')
