"""Opt-in page reuse; sequential discovery precedes bounded enrichment workers."""
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
import time
import threading
import uuid
from urllib.parse import quote,urlsplit,parse_qs,urlencode
import psycopg

from ingestion.ebay import Collector,SOURCE,ACCOUNT,ROOT,page_url,safe_url,comparison_order
from ingestion.website import db_kwargs,parse_time
from ingestion.acquisition import bounded_jobs,accept_element,ebay_complete,observed_subset
from ingestion.etsy_recovery import PageSetChanged


class EnrichmentChanged(ValueError):
    pass


class ReuseCollector(Collector):
    @staticmethod
    def cacheable(kind,payload):
        if not isinstance(payload,dict): return False
        if kind=='ebay_orders':
            return (isinstance(payload.get('orders'),list) and type(payload.get('total')) is int
                    and type(payload.get('limit')) is int and type(payload.get('offset')) is int)
        if kind=='ebay_order':
            return isinstance(payload.get('orderId'),str) and isinstance(payload.get('lineItems'),list)
        if kind=='ebay_fulfillments':
            return isinstance(payload.get('fulfillments'),list) and type(payload.get('total')) is int
        return isinstance(payload.get('fulfillmentId'),str)

    def raw(self,url,kind,body,status,headers,metadata):
        return super().raw(url,kind,body,status,{k.lower():v for k,v in headers.items()},metadata)

    def cooldown(self):
        rows=self.conn.execute('''SELECT sanitized_headers,metadata->>'fetched_at'
            FROM raw.raw_records WHERE source_system=%s AND source_account_id=%s
            AND response_status IN (429,503) AND sanitized_headers ?| ARRAY['retry-after','Retry-After']
            AND metadata->>'fetched_at'>=%s''',
            (SOURCE,ACCOUNT,(datetime.now(timezone.utc)-timedelta(days=366)).isoformat())).fetchall()
        self.conn.commit()
        remaining=0
        for row in rows:
            value=row[0].get('retry-after',row[0].get('Retry-After'))
            try: delay=float(value)
            except ValueError:
                delay=(parsedate_to_datetime(value)-parse_time(row[1])).total_seconds()
            if not 0<=delay<=31536000: raise RuntimeError('unsupported source Retry-After')
            remaining=max(remaining,delay-(datetime.now(timezone.utc)-parse_time(row[1])).total_seconds())
        if remaining>60: raise RuntimeError('source cooldown exceeds bounded cycle')
        if remaining>0: time.sleep(remaining)

    def get(self,url,kind,metadata=None):
        safe_url(url,self.args.origin)
        metadata=dict(metadata or {})
        if kind=='ebay_orders':
            metadata.setdefault('request_phase','discovery')
            if metadata['request_phase']=='discovery': metadata['collection_scan']=self.scan
        else: metadata.setdefault('request_phase',{'ebay_order':'order_detail','ebay_fulfillments':
                                                   'fulfillment_collection','ebay_fulfillment':'fulfillment_detail'}[kind])
        rows=self.conn.execute('''SELECT raw_record_id,parsed_payload,response_status,metadata
            FROM raw.raw_records WHERE run_id=%s AND resource_locator=%s ORDER BY acquired_at,raw_record_id''',
            (self.run_id,url)).fetchall()
        self.conn.commit()
        cached=next((r for r in reversed(rows) if r[2]==200 and self.cacheable(kind,r[1])
                     and all(r[3].get(k)==v for k,v in metadata.items())),None)
        if cached:
            if not isinstance(cached[1],dict): raise ValueError('cached response is not an object')
            return cached[:2]
        if len(rows)>=5: raise RuntimeError('retained HTTP attempt budget exhausted')
        # Base get() still audits each physical attempt. Offset its local budget
        # rather than allocating five new attempts on collection reentry.
        self.prior_attempts=len(rows)
        self.cooldown()
        return super().get(url,kind,metadata)

    def lookup_ids(self,identities):
        if (not isinstance(identities,(list,tuple)) or not 1<=len(identities)<=50
                or any(not isinstance(i,str) or not i for i in identities)
                or len(set(identities))!=len(identities)):
            raise ValueError('grouped lookup requires1..50 unique IDs')
        ids=sorted(identities)
        raw,payload=self.get(self.args.origin+ROOT+'?'+urlencode({'orderIds':','.join(ids)}),
                             'ebay_orders',dict(request_phase='order_ids',requested_order_ids=ids,collection_scan=self.scan))
        values=payload.get('orders')
        if not isinstance(values,list) or len(values)!=len(ids): raise ValueError('incomplete grouped lookup')
        returned=[self.order(value) for value in values]
        if len(set(returned))!=len(ids) or set(returned)!=set(ids): raise ValueError('unexpected grouped membership')
        if any(not self.args.window_start<=parse_time(v['lastModifiedDate'])<=self.args.window_end for v in values):
            raise ValueError('grouped lookup changed collection window; reconcile')
        return raw,values

    def acquire(self):
        row=self.conn.execute('''SELECT s.scan_number,s.status,
            EXISTS(SELECT 1 FROM ops.ebay_scan_restarts r WHERE (r.run_id,r.scan_number)=(s.run_id,s.scan_number))
            FROM ops.ebay_collection_scans s WHERE s.run_id=%s ORDER BY s.scan_number DESC LIMIT 1''',(self.run_id,)).fetchone()
        self.scan=row[0]+1 if row and (row[1]=='INVALID' or row[2]) else row[0] if row else 1
        if self.scan>5: raise RuntimeError('discovery scan budget exhausted')
        self.conn.execute('''INSERT INTO ops.ebay_collection_scans(run_id,scan_number)
            VALUES(%s,%s) ON CONFLICT DO NOTHING''',(self.run_id,self.scan))
        self.conn.commit()
        try: jobs=self.discover()
        except PageSetChanged:
            self.conn.execute("UPDATE ops.ebay_collection_scans SET status='INVALID',finished_at=clock_timestamp() WHERE run_id=%s AND scan_number=%s AND status='RUNNING'",(self.run_id,self.scan))
            self.conn.commit()
            raise
        self.conn.execute("UPDATE ops.ebay_collection_scans SET status='VALIDATED',finished_at=clock_timestamp() WHERE run_id=%s AND scan_number=%s AND status='RUNNING'",(self.run_id,self.scan))
        self.conn.commit()
        version_conflict=threading.Event()
        def worker(next_job):
            with psycopg.connect(**db_kwargs('PLATFORM','data_platform','platform_ingest'),
                                 connect_timeout=5,options='-c statement_timeout=15000 -c lock_timeout=10000') as own:
                collector=ReuseCollector(own,self.args,self.run_id)
                collector.scan=self.scan
                while (job:=next_job()) is not None:
                    try: collector.enrich(*job)
                    except EnrichmentChanged:
                        version_conflict.set()
                        raise
        try:
            bounded_jobs(jobs,self.args.detail_workers,worker)
        except Exception as error:
            if isinstance(error,EnrichmentChanged) or version_conflict.is_set():
                self.conn.execute('INSERT INTO ops.ebay_scan_restarts(run_id,scan_number) VALUES(%s,%s) ON CONFLICT DO NOTHING',
                                  (self.run_id,self.scan))
                self.conn.commit()
            raise
        pending=self.conn.execute('''SELECT 1 FROM ops.processing_work WHERE dedupe_key LIKE %s
            AND state<>'SUCCEEDED' LIMIT 1''',(f'm05:{self.run_id}:scan:{self.scan}:%',)).fetchone()
        self.conn.commit()
        if pending: raise RuntimeError('required enrichment unresolved; checkpoint unchanged')

    def discover(self):
        offset,total,seen,jobs=0,None,set(),[]
        while True:
            url=page_url(self.args.origin,self.args.window_start,self.args.window_end,offset,self.page_size)
            raw,p=self.get(url,'ebay_orders')
            if (type(p.get('total')) is not int or not 0<=p['total']<=1000
                    or type(p.get('limit')) is not int or p['limit']!=self.page_size
                    or type(p.get('offset')) is not int or p['offset']!=offset or not isinstance(p.get('orders'),list)):
                raise ValueError('malformed discovery envelope')
            if total is not None and p['total']!=total: raise PageSetChanged('mutable page total')
            total=p['total']
            if len(p['orders'])!=min(self.page_size,max(0,total-offset)): raise PageSetChanged('incomplete discovery page')
            expected=urlsplit(url)
            href=urlsplit(safe_url(p['href'],self.args.origin,ROOT))
            if parse_qs(href.query)!=parse_qs(expected.query): raise ValueError('page href changed scope')
            for index,value in enumerate(p['orders']):
                if (not isinstance(value,dict) or not isinstance(value.get('orderId'),str)
                        or not value['orderId'] or value.get('sellerId')!=ACCOUNT):
                    raise ValueError('missing discovery identity or seller mismatch')
                identity=value['orderId']
                if not self.args.window_start<=parse_time(value['lastModifiedDate'])<=self.args.window_end:
                    raise ValueError('order outside window')
                if identity in seen: raise PageSetChanged('duplicate discovery membership')
                seen.add(identity)
                work=uuid.uuid5(self.run_id,f'{self.scan}:{identity}')
                self.conn.execute('''INSERT INTO ops.processing_work
                    (work_id,dedupe_key,work_type,source_system,source_account_id,source_entity_id,
                     trigger_raw_record_id,state,created_at,updated_at)
                    VALUES(%s,%s,'EBAY_ORDER_DETAILS',%s,%s,%s,%s,'PENDING',%s,%s) ON CONFLICT DO NOTHING''',
                    (work,f'm05:{self.run_id}:scan:{self.scan}:{identity}',SOURCE,ACCOUNT,identity,raw,
                     self.args.observed_at,self.args.observed_at))
                jobs.append((work,identity,value,raw,index))
            self.conn.commit()
            if self.args.fail_after_page and offset==0: raise RuntimeError('intentional interruption after page/work')
            offset+=len(p['orders'])
            if offset>=total:
                if p.get('next'): raise ValueError('unexpected next link')
                return jobs
            next_url=urlsplit(safe_url(p['next'],self.args.origin,ROOT))
            expected=urlsplit(page_url(self.args.origin,self.args.window_start,self.args.window_end,offset,self.page_size))
            if parse_qs(next_url.query)!=parse_qs(expected.query): raise ValueError('next link changed scope')

    def enrich(self,work,identity,listed,page_raw,index):
        state=self.conn.execute('SELECT state FROM ops.processing_work WHERE work_id=%s',(work,)).fetchone()
        self.conn.commit()
        if state and state[0]=='SUCCEEDED': return
        path=ROOT+'/'+quote(identity,safe='')
        reuse=ebay_complete(listed)
        order_raw,order=page_raw,listed
        if not reuse:
            order_raw,order=self.get(self.args.origin+path,'ebay_order',{'order_id':identity})
            # Missing list fields may be filled by one actual detail response.
            # Conflicting observed fields still refuse; no merged order payload.
            compared_list=dict(listed,lineItems=listed.get('lineItems',[]))
            compared_full=comparison_order(order)
            compared_list=comparison_order(compared_list)
            if 'lineItems' not in listed: compared_list.pop('lineItems')
            if order.get('orderId')!=identity or not observed_subset(compared_list,compared_full):
                raise EnrichmentChanged('discovery/detail version conflict; no synthetic snapshot')
            self.order(order)
        else:
            self.order(order)
        metadata=dict(order_id=identity,order_raw_id=str(order_raw))
        _,shipping=self.get(self.args.origin+path+'/shipping_fulfillment','ebay_fulfillments',metadata)
        values=shipping.get('fulfillments')
        if (not isinstance(values,list) or type(shipping.get('total')) is not int
                or shipping['total']!=len(values) or any(not isinstance(v,dict) for v in values)):
            raise ValueError('incomplete shipping collection')
        ids=[v.get('fulfillmentId') for v in values]
        if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)): raise ValueError('invalid fulfillment identity')
        hrefs={self.args.origin+path+'/shipping_fulfillment/'+quote(i,safe='') for i in ids}
        if set(order.get('fulfillmentHrefs',[]))!=hrefs: raise EnrichmentChanged('shipping version/reference conflict')
        for value in values:
            # Only documented complete collection elements avoid a detail GET.
            if not all(k in value for k in ('fulfillmentId','shippedDate','lineItems')):
                href=self.args.origin+path+'/shipping_fulfillment/'+quote(value['fulfillmentId'],safe='')
                _,full=self.get(href,'ebay_fulfillment',metadata)
                if (not all(k in full for k in ('fulfillmentId','shippedDate','lineItems'))
                        or not observed_subset(value,full)):
                    raise EnrichmentChanged('incomplete/changed fulfillment; reconcile before publication')
                value=full
            if value.get('shippedDate') and parse_time(value['shippedDate'])>parse_time(order['lastModifiedDate']):
                raise EnrichmentChanged('shipping is newer than observed order version')
        if reuse: accept_element(self.conn,page_raw,identity,index,self.run_id,self.scan)
        self.conn.execute("UPDATE ops.processing_work SET state='SUCCEEDED',cycle_attempts=1,updated_at=%s WHERE work_id=%s",(self.args.observed_at,work))
        self.conn.commit()
