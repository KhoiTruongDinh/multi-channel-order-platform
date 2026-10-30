"""Bounded SQL report panels; no fixtures, cached results or all-order fetch."""
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(host=os.environ.get('PLATFORM_DB_HOST','postgres'),
        port=int(os.environ.get('PLATFORM_DB_PORT','5432')),dbname='data_platform',user='platform_report',
        password=os.environ['PLATFORM_REPORT_PASSWORD'],connect_timeout=5,
        options='-c statement_timeout=10000',row_factory=dict_row)


def scope(row):
    return f"{row['source_system']} / {row['source_account_id']}"


def transaction(c):
    c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')


@dataclass(frozen=True)
class Filters:
    scopes: tuple
    currency: str
    start: object
    end: object
    order_id: str = ''
    group: str = 'all'
    reason: str = ''
    product: str = ''

    def __post_init__(self):
        if not 0 <= (self.end-self.start).days < 366:
            raise ValueError('Choose 1..366 inclusive UTC dates')
        if self.group not in ('all','review','canceled','data'):
            raise ValueError('Unsupported worklist')
        if len(self.scopes)>100 or len(self.order_id)>256 or len(self.product)>256:
            raise ValueError('Filter exceeds supported size')


def options(factory=connect):
    with factory() as c:
        transaction(c)
        return dict(scopes=c.execute('SELECT source_system,source_account_id FROM report.live_source_health ORDER BY 1,2 LIMIT 100').fetchall(),
            dates=c.execute("SELECT min(source_created_at AT TIME ZONE 'UTC')::date AS first,max(source_created_at AT TIME ZONE 'UTC')::date AS last FROM report.orders_current").fetchone(),
            currencies=[r['currency'] for r in c.execute('SELECT DISTINCT currency FROM report.orders_current ORDER BY 1 LIMIT 20').fetchall()])


def where(f):
    pairs=[s.split(' / ',1) for s in f.scopes]
    sql='''(o.source_system,o.source_account_id) IN (SELECT * FROM unnest(%s::text[],%s::text[]))
        AND o.currency=%s AND o.source_created_at>=%s AND o.source_created_at<%s'''
    params=[[s[0] for s in pairs],[s[1] for s in pairs],f.currency,
        datetime.combine(f.start,time.min,timezone.utc),datetime.combine(f.end+timedelta(days=1),time.min,timezone.utc)]
    if f.order_id:
        sql+=' AND o.source_order_id=%s'
        params.append(f.order_id)
    if f.group=='review':
        sql+=' AND cardinality(o.review_reasons)>0'
    elif f.group=='canceled':
        sql+=" AND o.cancellation_state='CANCELED'"
    elif f.group=='data':
        sql+=' AND o.data_issue'
    if f.reason:
        sql+=' AND %s=ANY(o.review_reasons)'
        params.append(f.reason)
    return sql,params


COLUMNS='''o.source_system,o.source_account_id,o.source_order_id,o.source_created_at,o.source_updated_at,
 o.source_snapshot_observed_at,o.payment_state,o.fulfillment_state,o.cancellation_state,o.currency,
 o.source_order_total_amount,o.published_batch_id,o.review_reasons,o.data_issue'''
KEYS=('source_created_at','source_system','source_account_id','source_order_id')
JOIN='(l.source_system,l.source_account_id,l.source_order_id)=(o.source_system,o.source_account_id,o.source_order_id)'


def page_query(c,f,after=None,size=50):
    if not 1<=size<=100:
        raise ValueError('Page size must be 1..100')
    sql,params=where(f)
    if after:
        sql+=' AND (o.source_created_at,o.source_system,o.source_account_id,o.source_order_id)<(%s,%s,%s,%s)'
        params+=list(after)
    return c.execute(f'''SELECT {COLUMNS} FROM report.operations_orders o WHERE {sql}
        ORDER BY o.source_created_at DESC,o.source_system DESC,o.source_account_id DESC,o.source_order_id DESC LIMIT %s''',params+[size+1]).fetchall()


def business(f,cursor=None,selected=None,size=50,factory=connect):
    with factory() as c:
        transaction(c)
        return business_query(c,f,cursor,selected,size)


def business_query(c,f,cursor=None,selected=None,size=50):
    """UI calls business(); exposed connection supports rollback-only benchmarks."""
    meta=c.execute("SELECT current_timestamp AS read_at,current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS read_only").fetchone()
    publications=c.execute('SELECT * FROM report.publication_state ORDER BY publication_name').fetchall()
    signature=hashlib.sha256(json.dumps([asdict(f),publications],sort_keys=True,default=str).encode()).hexdigest()
    reset=bool(cursor and cursor['signature']!=signature)
    rows=page_query(c,f,cursor['after'] if cursor and not reset else None,size)
    more=len(rows)>size
    rows=rows[:size]
    next_cursor=dict(signature=signature,after=tuple(rows[-1][k] for k in KEYS)) if more else None
    sql,params=where(f)
    def query(columns,tail='',extra='',arguments=None):
        return c.execute(f'SELECT {columns} FROM report.operations_orders o WHERE {sql} {extra} {tail}',params if arguments is None else arguments)
    summary=query('''count(*) AS orders,count(*) FILTER(WHERE cardinality(review_reasons)>0) AS reviews,
        count(*) FILTER(WHERE cancellation_state='CANCELED') AS canceled,count(*) FILTER(WHERE data_issue) AS data_issues,
        CASE WHEN count(*) FILTER(WHERE source_order_total_amount IS NULL)>0 THEN NULL ELSE coalesce(sum(source_order_total_amount),0) END AS order_amount''').fetchone()
    channels=query('source_system,source_account_id,count(*) AS orders,count(*) FILTER(WHERE cardinality(review_reasons)>0) AS reviews',
        'GROUP BY 1,2 ORDER BY 1,2').fetchall()
    series=query("(source_created_at AT TIME ZONE 'UTC')::date AS day,source_system,count(*) AS orders",'GROUP BY 1,2 ORDER BY 1,2').fetchall()
    reasons=query('unnest(review_reasons) AS reason,count(*) AS orders','GROUP BY 1 ORDER BY 1').fetchall()
    fulfillment=query("source_system,coalesce(fulfillment_state,'UNKNOWN') AS fulfillment,count(*) AS orders",'GROUP BY 1,2 ORDER BY 1,2',
        "AND cancellation_state IS DISTINCT FROM 'CANCELED'").fetchall()
    product_sql=" AND coalesce(l.canonical_variant_id,'__UNMAPPED__')=%s" if f.product else ''
    lp=params+([f.product] if f.product else [])
    base=f'FROM report.operations_orders o JOIN report.order_lines_current l ON {JOIN} WHERE {sql} {product_sql}'
    money="CASE WHEN count(*) FILTER(WHERE l.line_gross_amount IS NULL)>0 THEN NULL ELSE coalesce(sum(l.line_gross_amount),0) END"
    lines=c.execute(f'SELECT count(*) AS lines,coalesce(sum(l.quantity),0) AS units,{money} AS merchandise {base}',lp).fetchone()
    products=c.execute(f"SELECT coalesce(l.canonical_variant_id,'__UNMAPPED__') AS product,sum(l.quantity) AS units,{money} AS merchandise {base} GROUP BY 1 ORDER BY units DESC,product LIMIT 20",lp).fetchall()
    channel_lines=c.execute(f'SELECT l.source_system,l.source_account_id,coalesce(sum(l.quantity),0) AS units,{money} AS merchandise {base} GROUP BY 1,2',lp).fetchall()
    versions=c.execute(f'''SELECT h.source_system,h.source_account_id,count(*) AS versions FROM report.order_observed_history h
        JOIN report.operations_orders o USING(source_system,source_account_id,source_order_id)
        WHERE {sql} GROUP BY 1,2 ORDER BY 1,2''',params).fetchall()
    for row in channels:
        activity=next((r for r in channel_lines if (r['source_system'],r['source_account_id'])==(row['source_system'],row['source_account_id'])),{})
        row.update(units=activity.get('units',0),merchandise=activity.get('merchandise',0))
        row['versions']=sum(r['versions'] for r in versions if (r['source_system'],r['source_account_id'])==(row['source_system'],row['source_account_id']))
    detail=None
    if selected and not reset:
        order=query(COLUMNS,extra='AND (o.source_system,o.source_account_id,o.source_order_id)=(%s,%s,%s)',arguments=params+list(selected)).fetchone()
        if order:
            detail=dict(order=order)
            for name,view,sort in [('lines','order_lines_current','source_line_id'),('history','order_observed_history','source_updated_at,first_observed_at,snapshot_id'),
                    ('allocations','line_shipment_allocations','source_line_id,fulfillment_id')]:
                found=c.execute(f'''SELECT * FROM report.{view} WHERE (source_system,source_account_id,source_order_id)=(%s,%s,%s)
                    ORDER BY {sort} LIMIT 101''',selected).fetchall()
                detail[name],detail[name+'_truncated']=found[:100],len(found)>100
    return dict(metadata=meta,publications=publications,signature=signature,reset=reset,rows=rows,next_cursor=next_cursor,summary=summary,
        channels=channels,series=series,reasons=reasons,fulfillment=fulfillment,lines=lines,products=products,versions=versions,detail=detail,
        health=c.execute('SELECT * FROM report.live_source_health ORDER BY source_system,source_account_id LIMIT 100').fetchall())


def monitoring(scopes,hours=24,mode='all',factory=connect):
    if hours not in (1,6,24,168) or mode not in ('all','runtime','s01'):
        raise ValueError('Unsupported monitoring window/mode')
    pairs=[s.split(' / ',1) for s in scopes]
    predicate='(source_system,source_account_id) IN (SELECT * FROM unnest(%s::text[],%s::text[]))'
    params=[[s[0] for s in pairs],[s[1] for s in pairs]]
    with factory() as c:
        transaction(c)
        now=c.execute('SELECT current_timestamp AS now').fetchone()['now']
        timed=predicate+' AND started_at>=%s'
        tp=params+[now-timedelta(hours=hours)]
        if mode!='all':
            timed+=' AND validation_mode=%s'
            tp.append(mode)
        aggregate=c.execute(f'''SELECT source_system,stage,count(*) AS attempts,count(*) FILTER(WHERE outcome='RUNNING') AS recorded_running,
            count(*) FILTER(WHERE outcome<>'RUNNING') AS terminal,
            count(*) FILTER(WHERE outcome IN ('FAILED','TIMED_OUT','INTERRUPTED')) AS errors,
            count(duration_ms) AS duration_samples,percentile_cont(0.5) WITHIN GROUP(ORDER BY duration_ms) AS p50_ms,
            percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms) AS p95_ms
            FROM report.execution_measurements WHERE {timed} GROUP BY 1,2 ORDER BY 1,2''',tp).fetchall()
        series=c.execute(f'''SELECT date_bin(interval '5 minutes',started_at,timestamptz '2000-01-01') AS bucket,
            source_system,stage,outcome,count(*) AS attempts,avg(duration_ms) AS mean_ms
            FROM report.execution_measurements WHERE {timed} GROUP BY 1,2,3,4 ORDER BY 1,2,3,4''',tp).fetchall()
        result=dict(now=now,aggregate=aggregate,series=series)
        for name,view,extra,sort,args in [
            ('measurements','execution_measurements',timed,'started_at DESC,measurement_id',tp),
            ('scheduler','scheduler_observations',predicate,'dag_id',params),('backlog','work_backlog',predicate,'source_system,state',params),
            ('runs','live_runs',predicate+' AND started_at>=%s','started_at DESC,run_id',params+[now-timedelta(hours=hours)]),
            ('tests','live_test_outcomes',predicate+' AND manifest_frozen_at>=%s','manifest_frozen_at DESC,batch_id',params+[now-timedelta(hours=hours)]),
            ('exceptions','live_exceptions',predicate+' AND last_seen_at>=%s','last_seen_at DESC,exception_id',params+[now-timedelta(hours=hours)])]:
            result[name]=c.execute(f'SELECT * FROM report.{view} WHERE {extra} ORDER BY {sort} LIMIT 100',args).fetchall()
        return result


def scheduler_status(row,now):
    if not row['observed_at'] or (now-row['observed_at']).total_seconds()>90:
        return 'Unknown / stale sample'
    heartbeat=row['scheduler_heartbeat_at']
    if not heartbeat or (now-heartbeat).total_seconds()>120:
        return 'Unknown / stale scheduler'
    return 'Paused' if row['is_paused'] else 'Enabled (not a success guarantee)'
