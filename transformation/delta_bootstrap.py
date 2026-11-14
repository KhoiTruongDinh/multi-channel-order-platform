"""Explicit cold deployment check: full dbt parity BEFORE delta publication.

Requires a drained deployment. Never called automatically by a polling DAG.
Frozen raw, source identity and durable build attempts remain owned by runtime.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from transformation.delta_runtime import source_lock,freeze,build
from transformation.delta_publish import audited_publish
from transformation.delta_plan import ROOT,load
from transformation.publish import COPIES
from transformation.source_config import SOURCES


def full_oracle(conn,plan,batch):
    from psycopg import sql
    prefix=SOURCES[plan['source']][1]
    target=Path(tempfile.gettempdir())/'delta-bootstrap-check'/str(batch)
    variables=dict(batch_id=str(batch),release_source=plan['source'],
        mapping_version=plan['mapping_version'],transformation_version=plan['transformation_version'],validation_mode='runtime')
    command=[str(Path(sys.executable).with_name('dbt')),'build',
        '--project-dir',str(ROOT/'transformations'),'--profiles-dir',str(ROOT/'infra/dbt'),
        '--target-path',str(target),'--log-path',str(target/'logs'),'--vars',json.dumps(variables)]
    done=subprocess.run(command,capture_output=True,text=True)
    if done.returncode:
        raise RuntimeError('cold full-dbt oracle failed: '+done.stdout[-4000:])
    report=json.loads((target/'run_results.json').read_text())
    assert report['results'] and all(r['status'] in ('success','pass') for r in report['results'])
    comparisons=[]
    for stable,base in COPIES:
        name=base.split('.')[1].replace('candidate_',prefix+'candidate_',1)
        private=sql.Identifier(plan['schema'],name)
        ordinary=sql.Identifier('build',name)
        # Same frozen batch/versions: compare ALL columns, including lineage.
        difference=conn.execute(sql.SQL('''SELECT count(*) FROM
            ((SELECT * FROM {} EXCEPT ALL SELECT * FROM {})
             UNION ALL (SELECT * FROM {} EXCEPT ALL SELECT * FROM {})) d''').format(
                private,ordinary,ordinary,private)).fetchone()[0]
        assert difference==0,(stable,difference)
        comparisons.append(stable)
    conn.commit()
    history=sql.Identifier(plan['schema'],prefix+'candidate_order_snapshot_history')
    lost=conn.execute(sql.SQL('''SELECT count(*) FROM core.order_snapshot_history o
        LEFT JOIN {} n USING(snapshot_id) WHERE o.source_system=%s AND
        (n.snapshot_id IS NULL OR (o.source_updated_at,o.content_fingerprint,o.first_observed_at)
          IS DISTINCT FROM (n.source_updated_at,n.content_fingerprint,n.first_observed_at))''').format(history),
        (plan['source'],)).fetchone()[0]
    assert lost==0,'cold bootstrap would drop/change an already observed source version'
    conn.commit()
    return dict(status='PASS',compared=comparisons,
        preserved_observed_source_versions=True,
        nodes=[dict(id=r['unique_id'],status=r['status'],seconds=r['execution_time']) for r in report['results']])


def verified_bootstrap(plan,batch,run,publisher,attempt=1):
    started=time.monotonic()
    with source_lock(plan) as conn:
        # Cold oracle touches the legacy build schema; keep manual legacy work out.
        assert conn.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0], 'legacy release is busy'
        conn.commit()
        freeze(conn,plan,batch,run,bootstrap=True)
        build(conn,plan,batch,attempt=attempt)
        state=conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(batch,)).fetchone()[0]
        conn.commit()
        if state=='PUBLISHED':
            return dict(status='ALREADY_PUBLISHED',batch=str(batch))
        oracle=full_oracle(conn,plan,batch)
        audited_publish(plan,batch,publisher)
    return dict(status='PUBLISHED',source=plan['source'],batch=str(batch),
        plan_sha256=plan['plan_sha256'],cold_seconds=time.monotonic()-started,full_dbt_oracle=oracle)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True)
    for name in ('batch-id','run-id','publish-run-id'):
        parser.add_argument('--'+name,required=True,type=uuid.UUID)
    parser.add_argument('--attempt',type=int,choices=range(1,6),default=1)
    args=parser.parse_args()
    print(json.dumps(verified_bootstrap(load(args.plan),args.batch_id,args.run_id,args.publish_run_id,args.attempt)))
