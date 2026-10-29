"""Rollback-only fencing/budget tests, using real HTTP against the local API."""
import uuid
from ingestion.etsy_common import connect, enqueue
from ingestion.etsy import claim, process, expire_exhausted,require_recovery_allowed


class RollbackOnly:
    def __init__(self, connection):
        self.connection=connection
    def execute(self,*args,**kwargs):
        return self.connection.execute(*args,**kwargs)
    def commit(self):
        pass
    def rollback(self):
        pass


c=connect()
try:
    proxy=RollbackOnly(c)
    work=enqueue(c,'lease-test:'+uuid.uuid4().hex,9001001,None)
    old=claim(proxy,[work])
    c.execute("UPDATE ops.processing_work SET lease_until=clock_timestamp()-INTERVAL '1 second' WHERE work_id=%s",(work,))
    new=claim(proxy,[work])
    assert old[-1]!=new[-1] and new[3]==2
    try:
        process(proxy,old)
    except RuntimeError as error:
        assert 'lease lost' in str(error),str(error)
    else:
        raise AssertionError('stale owner completed work')
    assert c.execute("SELECT count(*) FROM raw.raw_records WHERE run_id=%s AND resource_type='etsy_receipt'",(new[1],)).fetchone()[0]==0
    assert process(proxy,new)
    try:
        with c.transaction():
            c.execute('UPDATE ops.processing_work SET cycle_attempts=0 WHERE work_id=%s',(work,))
    except Exception as error:
        assert 'immutable' in str(error),str(error)
    else:
        raise AssertionError('budget was reset')
    work2=enqueue(c,'lease-exhaustion:'+uuid.uuid4().hex,9001001,None)
    for number in range(1,6):
        lease=claim(proxy,[work2])
        assert lease[3]==number
        c.execute("UPDATE ops.processing_work SET lease_until=clock_timestamp()-INTERVAL '1 second' WHERE work_id=%s",(work2,))
    expire_exhausted(proxy)
    assert claim(proxy,[work2]) is None
    assert c.execute('SELECT state,cycle_attempts FROM ops.processing_work WHERE work_id=%s',(work2,)).fetchone()==('FAILED',5)
    try:
        require_recovery_allowed(c,9001001)
    except RuntimeError as error:
        assert 'explicit controlled replay' in str(error),str(error)
    else:
        raise AssertionError('scheduled recovery could reset an exhausted receipt budget')
    replay=enqueue(c,'explicit-replay-test:'+uuid.uuid4().hex,9001001,None,replay_of=work2)
    replay_lease=claim(proxy,[replay])
    assert process(proxy,replay_lease)
    require_recovery_allowed(c,9001001)
    try:
        with c.transaction():
            c.execute("UPDATE ops.etsy_work_context SET cycle_id='changed' WHERE work_id=%s",(work,))
    except Exception as error:
        assert 'immutable' in str(error) or 'permission denied' in str(error),str(error)
    else:
        raise AssertionError('work context was mutable')
finally:
    c.rollback()
    c.close()
print('M06 lease reclaim/fencing + five-attempt exhaustion + context immutability PASS (all DB writes rolled back)')
