"""Test-only finite rate-window/backlog gates; no source or warehouse writes."""
from datetime import datetime,timedelta,timezone

from tools.s02_data.load import query
from test_support.s02_plan import literal

DAGS={'internal_web':('website_polling',),'ebay_sim':('ebay_polling',),
      'etsy_sim':('etsy_inbox','etsy_recovery')}


def at(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def progress(expected,rows,shift):
    """Rows include every wanted identity, even when current is absent."""
    clock=rows[0]['observed_at']; now=at(clock); channels={}
    for row in rows:
        key=tuple(row[k] for k in ('source_system','source_account_id','source_order_id'))
        due=at(expected[key][-1]['updated'])+timedelta(seconds=shift)
        matching=row['source_updated_at'] is not None and at(row['source_updated_at'])==due
        bucket=channels.setdefault(key[0],dict(orders=0,matching_final=0,eligible_final=0,
            eligible_not_current=0,oldest_pending_seconds=None))
        bucket['orders']+=1; bucket['matching_final']+=int(matching)
        if due<=now:
            bucket['eligible_final']+=1
            if not matching:
                bucket['eligible_not_current']+=1
                age=(now-due).total_seconds()
                bucket['oldest_pending_seconds']=max(bucket['oldest_pending_seconds'] or 0,age)
    return dict(observed_at=clock,by_source=channels,
        matching_final=sum(c['matching_final'] for c in channels.values()),
        eligible_not_current=sum(c['eligible_not_current'] for c in channels.values()))


class Envelope:
    def __init__(self,config,report):
        settings=config['campaign']; self.limits=settings['load']
        active=[(s,c) for s,c in config['channels'].items() if c['orders']]
        if config['profile']!='normal': raise ValueError('rate steps require normal source profile')
        if any((at(c['end_at'])-at(c['start_at'])).total_seconds()<360 for _,c in active):
            raise ValueError('rate steps require source intervals of at least360 seconds')
        start=min(at(c['start_at']) for _,c in active)
        self.end=max(at(c['end_at']) for _,c in active)
        if (self.end-start).total_seconds()+self.limits['max_drain_seconds']+60>settings['timeout_seconds']:
            raise ValueError('campaign timeout cannot cover rate window and drain budget')
        self.dags=sorted(d for s,_ in active for d in DAGS[s])
        self.value=dict(status='PREFLIGHT',limits=self.limits,required_dags=self.dags,
            exact_commit_latency='NOT_MEASURED',first_observed_drain_at=None)
        report['load_assessment']=self.value

    def admitted(self,since,shift):
        self.since=since; self.end+=timedelta(seconds=shift)
        self.value.update(status='OBSERVING',scheduled_window_end_at=self.end.isoformat())

    def observe(self,db,state,current):
        now=at(current['observed_at'])
        # A fixed eligibility window excludes historical and manual successes.
        runs=query(db,'''SELECT dag_id,run_id,state,start_date,end_date FROM dag_run
          WHERE dag_id IN ('''+','.join(map(literal,self.dags))+''') AND run_type='scheduled'
          AND start_date>='''+literal(self.since)+'''::timestamptz AND start_date<='''+
          literal(self.end.isoformat())+'''::timestamptz ORDER BY dag_id,start_date,run_id''','airflow_meta')
        deadline=self.end+timedelta(seconds=self.limits['max_drain_seconds'])
        counts={dag:sum(r['dag_id']==dag and r['state']=='success' and r['end_date'] is not None
                       and at(r['end_date'])<=deadline for r in runs) for dag in self.dags}
        drained=now>=self.end and state['reached_final_versions'] and current['eligible_not_current']==0
        if drained and self.value['first_observed_drain_at'] is None:
            self.value.update(first_observed_drain_at=current['observed_at'],
                observed_drain_seconds=(now-self.end).total_seconds())
        enough=all(n>=self.limits['min_scheduled_successes'] for n in counts.values())
        elapsed=(now-self.end).total_seconds()
        self.value.update(scheduled_runs=runs,scheduled_successes=counts,
            elapsed_after_window_seconds=elapsed,latest_final_progress=current)
        drain=self.value.get('observed_drain_seconds')
        if elapsed>self.limits['max_drain_seconds'] and (drain is None or not enough or drain>self.limits['max_drain_seconds']):
            self.value.update(status='FAIL',reason='observed drain/scheduled-cycle budget exceeded')
            raise RuntimeError('rate-step drain/scheduled-cycle budget exceeded; evidence retained')
        self.value['status']='PASS' if drained and enough else 'OBSERVING'

    def ready(self):
        return self.value['status']=='PASS'
