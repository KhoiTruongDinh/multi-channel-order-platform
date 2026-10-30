"""Rollback-only operational immutability and artifact-mode rejection checks."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import uuid

import yaml
from orchestration.website_workflow import connect
from transformation.batch import transition,connect as transform_connect


with connect() as c:
    row=c.execute('''SELECT p.run_id,p.requested_window_end,p.batch_id FROM ops.polling_cycles x
        JOIN ops.pipeline_runs p USING(run_id) JOIN ops.transform_batches b ON p.batch_id=b.batch_id
        WHERE b.status='PUBLISHED' ORDER BY p.started_at DESC LIMIT 1''').fetchone()
    assert row,'Run a successful polling cycle first'
    run_id,end,batch=row
    assert not c.execute("SELECT has_table_privilege('platform_ingest','ops.polling_cycles','UPDATE')").fetchone()[0]
    try:
        with c.transaction():
            # M06 adds windowless drain cycles: NULL + interval is still NULL,
            # not a mutation. COALESCE exercises a genuine change for both kinds.
            c.execute("UPDATE ops.pipeline_runs SET requested_window_end=coalesce(requested_window_end,clock_timestamp())+INTERVAL '1 second' WHERE run_id=%s",(run_id,))
    except Exception as error:
        assert 'immutable' in str(error),str(error)
    else:
        raise AssertionError('polling bound was mutable')
    assert c.execute('SELECT requested_window_end FROM ops.pipeline_runs WHERE run_id=%s',(run_id,)).fetchone()[0]==end

root=Path('/opt/project/transformations/target')/str(batch)
with transform_connect() as c:
    try:
        with c.transaction():
            c.execute("UPDATE ops.transform_batches SET validation_mode='s01' WHERE batch_id=%s",(batch,))
    except Exception as error:
        assert 'immutable' in str(error),str(error)
    else:
        raise AssertionError('frozen validation mode was mutable')
report=json.loads((root/'run_results.json').read_text())
variables=report['args']['vars']
if isinstance(variables,str):
    variables=yaml.safe_load(variables)
assert variables['validation_mode']=='runtime'
variables['validation_mode']='s01'
report['args']['vars']=variables
with tempfile.TemporaryDirectory() as temp:
    artifact=Path(temp)/'run_results.json'
    artifact.write_text(json.dumps(report))
    (Path(temp)/'manifest.json').write_bytes((root/'manifest.json').read_bytes())
    try:
        transition(argparse.Namespace(command='tested',batch_id=batch,artifact=str(artifact),
            require_injected_failure=False,expected_status='BUILDING'))
    except RuntimeError as error:
        assert 'validation mode differ' in str(error),str(error)
    else:
        raise AssertionError('artifact mode was not bound to frozen batch')
print('M05B immutable window/config + artifact validation mode PASS')
