"""Read-only PG-backed source reconstruction. No generator or oracle imports."""
import copy
from datetime import datetime, timezone
import os
import re


def split_document(source, document):
    """Factor source payload into immutable header/base and coherent collections."""
    p = copy.deepcopy(document)
    if source == 'ebay_sim':
        header = p['order']
        collections = dict(lineItems=header.pop('lineItems'), fulfillments=p['fulfillments'])
        changing = {k: header.pop(k) for k in ('lastModifiedDate','orderPaymentStatus','orderFulfillmentStatus','cancelStatus','fulfillmentHrefs')}
    elif source == 'etsy_sim':
        header = p
        collections = {k: header.pop(k) for k in ('transactions','shipments','refunds')}
        changing = {k: header.pop(k) for k in ('updated_timestamp','status','is_paid','is_shipped')}
    else:
        raise ValueError('not a marketplace source')
    return header, changing, collections


def assemble(source, base, header, collections):
    value = copy.deepcopy(base) | copy.deepcopy(header)
    if source == 'ebay_sim':
        value['lineItems'] = copy.deepcopy(collections['lineItems'])
        return dict(order=value, fulfillments=copy.deepcopy(collections['fulfillments']))
    return value | copy.deepcopy(collections)


class PostgresStore:
    def __init__(self, kind, connect=None):
        self.kind = kind
        self.source = {'ebay':'ebay_sim','etsy':'etsy_sim'}[kind]
        self.account = 'seller_sim_01' if kind == 'ebay' else '7001'
        self.campaign = os.environ['S02_CAMPAIGN_ID']
        if not re.fullmatch('[0-9a-f]{12}', self.campaign):
            raise ValueError('invalid campaign ID')
        self._connect = connect

    def connect(self):
        if self._connect:
            return self._connect()
        import psycopg
        return psycopg.connect(host=os.environ.get('S02_DB_HOST','postgres'), port=5432,
            dbname='marketplace_sim', user='s02_'+self.kind+'_reader',
            password=os.environ['S02_DB_PASSWORD'], connect_timeout=5,
            options='-c default_transaction_read_only=on -c statement_timeout=10000')

    def clock(self, cur=None):
        if cur is None:
            with self.connect() as conn:
                with conn.cursor() as cursor:
                    return self.clock(cursor)
        cur.execute("SELECT to_regclass('s02.local_datasets')")
        if cur.fetchone()[0] is not None:
            cur.execute('SELECT state FROM s02.local_datasets WHERE campaign_id=%s',(self.campaign,))
            local=cur.fetchone()
            if local:
                if local[0]!='READY': raise ValueError('local dataset not ready')
                cur.execute('SELECT logical_now,mode,logical_start,stopped_at FROM s02.playback_clock WHERE campaign_id=%s',(self.campaign,))
                row=cur.fetchone()
                if not row: raise ValueError('local dataset has no playback clock')
                cur.execute("SELECT min((c.value->>'start_at')::timestamptz) FROM s02.campaigns d, jsonb_each(d.config->'channels') c WHERE d.id=%s",(self.campaign,))
                initial=cur.fetchone()[0] or row[2]
                return dict(campaign_id=self.campaign,now=row[0].isoformat(),mode=row[1],
                            initial_start=initial.isoformat(),running=row[3] is None)
        cur.execute('SELECT statement_timestamp()')
        at=cur.fetchone()[0].isoformat()
        return dict(campaign_id=self.campaign,now=at,mode='realtime',initial_start=at,running=True)

    def query(self, *, identity=None, start=None, end=None, limit=50, offset=0):
        """Select latest BEFORE window filtering; capture one DB clock per request."""
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError('invalid page')
        with self.connect() as conn:
            with conn.cursor() as cur:
                at = datetime.fromisoformat(self.clock(cur)['now'])
                # identity filtering is safe before latest selection; time-window is not.
                cur.execute('''WITH latest AS (
                    SELECT DISTINCT ON (v.order_id) v.* FROM s02.versions v
                    JOIN s02.campaigns d ON d.id=v.campaign_id AND d.sealed
                    WHERE v.campaign_id=%s AND v.source=%s AND v.account_id=%s
                      AND v.visible_at<=%s AND (%s::text IS NULL OR v.order_id=%s)
                    ORDER BY v.order_id,v.visible_at DESC,v.sequence DESC
                ), filtered AS (
                    SELECT * FROM latest WHERE (%s::timestamptz IS NULL OR source_updated_at>=%s)
                      AND (%s::timestamptz IS NULL OR source_updated_at<=%s)
                ) SELECT o.base,v.header,c.body,count(*) OVER() FROM filtered v
                  JOIN s02.orders o USING(campaign_id,source,account_id,order_id)
                  JOIN s02.components c ON (c.campaign_id,c.source,c.account_id,c.order_id,c.digest)=
                    (v.campaign_id,v.source,v.account_id,v.order_id,v.component_digest)
                  ORDER BY v.source_updated_at,v.order_id LIMIT %s OFFSET %s''',
                    (self.campaign,self.source,self.account,at,identity,identity,start,start,end,end,limit,offset))
                rows = cur.fetchall()
                # count OVER is unavailable past the end: API count needs a separate
                # query with the SAME T, not an advancing clock or Python full scan.
                cur.execute('''SELECT count(*) FROM (
                    SELECT DISTINCT ON (order_id) source_updated_at FROM s02.versions v
                    JOIN s02.campaigns d ON d.id=v.campaign_id AND d.sealed
                    WHERE campaign_id=%s AND source=%s AND account_id=%s AND visible_at<=%s
                      AND (%s::text IS NULL OR order_id=%s)
                    ORDER BY order_id,visible_at DESC,sequence DESC
                ) t WHERE (%s::timestamptz IS NULL OR source_updated_at>=%s)
                    AND (%s::timestamptz IS NULL OR source_updated_at<=%s)''',
                    (self.campaign,self.source,self.account,at,identity,identity,start,start,end,end))
                total = cur.fetchone()[0]
        return [assemble(self.source,*r[:3]) for r in rows], total

    def get(self, identity):
        values, _ = self.query(identity=str(identity), limit=1)
        return values[0] if values else None


class LivePostgresStore(PostgresStore):
    """Actual-time append-only source across admitted batches; no campaign switch."""
    def __init__(self,kind,connect=None):
        self.kind=kind
        self.source={'ebay':'ebay_sim','etsy':'etsy_sim'}[kind]
        self.account='seller_sim_01' if kind=='ebay' else '7001'
        self._connect=connect

    def query(self,*,identity=None,start=None,end=None,limit=50,offset=0):
        if not 1<=limit<=200 or offset<0: raise ValueError('invalid page')
        # One snapshot/time for rows and count; eligibility before window filtering.
        cte='''WITH latest AS (
          SELECT DISTINCT ON(v.order_id) v.*,b.shift_seconds,
                 v.source_updated_at+make_interval(secs=>b.shift_seconds::double precision) AS effective_updated
          FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
          WHERE v.source=%s AND v.account_id=%s
            AND v.visible_at+make_interval(secs=>b.shift_seconds::double precision)<=%s
            AND (%s::text IS NULL OR v.order_id=%s)
          ORDER BY v.order_id,v.visible_at DESC,v.sequence DESC
        ), filtered AS (
          SELECT * FROM latest WHERE (%s::timestamptz IS NULL OR effective_updated>=%s)
            AND (%s::timestamptz IS NULL OR effective_updated<=%s)
        ) '''
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                cur.execute('SELECT statement_timestamp()'); at=cur.fetchone()[0]
                args=(self.source,self.account,at,identity,identity,start,start,end,end)
                cur.execute(cte+'''SELECT o.base,v.header,c.body,v.shift_seconds FROM filtered v
                  JOIN s02.orders o USING(campaign_id,source,account_id,order_id)
                  JOIN s02.components c ON (c.campaign_id,c.source,c.account_id,c.order_id,c.digest)=
                    (v.campaign_id,v.source,v.account_id,v.order_id,v.component_digest)
                  ORDER BY v.effective_updated,v.order_id LIMIT %s OFFSET %s''',args+(limit,offset))
                rows=cur.fetchall()
                cur.execute(cte+'SELECT count(*) FROM filtered',args); total=cur.fetchone()[0]
        from simulator.live_source import translate
        return [translate(assemble(self.source,*r[:3]),r[3]) for r in rows],total


def make_store(kind):
    mode = os.environ.get('SIMULATOR_MODE')
    if mode == 'live-pg':
        return LivePostgresStore(kind)
    if mode == 's02-pg':
        return PostgresStore(kind)
    if mode == 's02':
        from simulator.s02_store import Store
        return Store(kind)
    if mode not in (None, '', 's01'):
        raise ValueError('unknown simulator mode')
    return None
