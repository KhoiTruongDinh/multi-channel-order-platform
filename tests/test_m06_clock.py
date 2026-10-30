"""Force a backwards application clock through the actual shared stage lifecycle.

All DB writes roll back and the mocked stage performs no business operation.
"""
import argparse
from datetime import datetime,timedelta,timezone
import uuid
from unittest.mock import patch
from orchestration import website_workflow as w


class Clock:
    value=datetime.now(timezone.utc)
    @classmethod
    def now(cls,tz):
        return cls.value


class RollbackOnly:
    def __init__(self,c):
        self.c=c
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass
    def execute(self,*args,**kwargs):
        return self.c.execute(*args,**kwargs)
    def commit(self):
        pass
    def rollback(self):
        pass


execution='clock-regression-'+uuid.uuid4().hex
args=argparse.Namespace(execution_id=execution,workflow_id=w.identity(execution,'workflow'),
    batch_id=w.identity(execution,'batch'),source='etsy_sim',validation_mode='s01',window_start=None,window_end=None,dag_id=None)
c=w.connect()
def regress(*args):
    Clock.value-=timedelta(seconds=1)
try:
    with patch.object(w,'connect',return_value=RollbackOnly(c)),patch.object(w,'datetime',Clock),patch.object(w,'perform',side_effect=regress):
        w.run_stage(args,'publish')
    result=c.execute('''SELECT t.started_at,t.finished_at,p.started_at,p.finished_at
        FROM ops.task_attempts t JOIN ops.pipeline_runs p USING(run_id) WHERE p.run_id=%s''',(args.workflow_id,)).fetchone()
    assert result[0]==result[1] and result[2]==result[3],result
finally:
    c.rollback()
    c.close()
print('M06 shared lifecycle backwards-clock guard PASS (rollback-only, no source clock mutation)')
