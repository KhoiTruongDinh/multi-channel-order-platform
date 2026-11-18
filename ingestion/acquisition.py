"""Acquisition policy only: bounded workers, immutable options and real page refs."""
from concurrent.futures import ThreadPoolExecutor


def policy(mode='legacy', workers=1):
    if mode not in ('legacy','page-reuse') or type(workers) is not int or workers not in (1,2):
        raise ValueError('acquisition mode legacy/page-reuse; detail workers1 or2 required')
    if mode=='legacy' and workers!=1:
        raise ValueError('legacy acquisition retains one worker')
    return mode,workers


def bounded_jobs(jobs, workers, worker):
    """Only worker-count futures/clients/connections, not a future per order.

    Stop allocating after the first failure; join in-flight work before returning.
    Workers pull jobs serially; parent checkpoint cannot overtake.
    """
    if workers not in (1,2): raise ValueError('detail workers must be1 or2')
    if not jobs: return
    import threading
    cursor=iter(jobs); lock=threading.Lock(); stopped=threading.Event()
    def next_job():
        with lock:
            return None if stopped.is_set() else next(cursor,None)
    def run():
        try: worker(next_job)
        except BaseException:
            stopped.set()
            raise
    if workers==1: return run()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(run) for _ in range(workers)]
        for future in futures: future.result()


def pin_options(conn, run, mode, workers, size):
    from psycopg.types.json import Jsonb
    policy(mode,workers)
    settings=dict(mode=mode,workers=workers,page_size=size)
    existing=conn.execute('SELECT settings FROM ops.collection_options WHERE run_id=%s',(run,)).fetchone()
    if existing:
        if existing[0]!=settings: raise ValueError('collection options differ from retained cycle')
    else:
        if conn.execute('SELECT 1 FROM raw.raw_records WHERE run_id=%s LIMIT 1',(run,)).fetchone():
            raise ValueError('cannot change a legacy collection to page reuse on retry')
        conn.execute('INSERT INTO ops.collection_options(run_id,settings) VALUES(%s,%s)',(run,Jsonb(settings)))
    conn.commit()


def check_legacy_options(conn,run):
    if conn.execute("SELECT to_regclass('ops.collection_options')").fetchone()[0]:
        if conn.execute('SELECT 1 FROM ops.collection_options WHERE run_id=%s',(run,)).fetchone():
            raise ValueError('retained collection requires its pinned page-reuse options')


def accept_element(conn, raw, identity, index, run, scan):
    conn.execute('''INSERT INTO ops.acquisition_elements
        (raw_record_id,source_entity_id,element_index,collection_run_id,scan_number)
        VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(raw,str(identity),index,run,scan))


def etsy_complete(value):
    """Structural completeness, NOT business conversion/normalization."""
    if not isinstance(value,dict): return False
    required=('receipt_id','is_paid','is_shipped','status','transactions','shipments',
              'subtotal','discount_amt','total_shipping_cost','total_tax_cost','grandtotal')
    if any(k not in value for k in required): return False
    if type(value['receipt_id']) is not int or value['receipt_id']<=0: return False
    if not any(k in value for k in ('created_timestamp','create_timestamp')): return False
    if not any(k in value for k in ('updated_timestamp','update_timestamp')): return False
    return isinstance(value['transactions'],list) and isinstance(value['shipments'],list)


def ebay_complete(value):
    if not isinstance(value,dict): return False
    required=('orderId','sellerId','creationDate','lastModifiedDate','lineItems',
              'orderPaymentStatus','orderFulfillmentStatus','pricingSummary','fulfillmentHrefs')
    summary=value.get('pricingSummary')
    lines=value.get('lineItems')
    cancel=value.get('cancelStatus')
    return (all(k in value for k in required) and isinstance(summary,dict)
            and all(isinstance(summary.get(k),dict) and all(f in summary[k] for f in ('value','currency'))
                    for k in ('priceSubtotal','total'))
            and isinstance(lines,list) and bool(lines)
            and all(isinstance(l,dict) and all(k in l for k in ('lineItemId','quantity','lineItemCost')) for l in lines)
            and isinstance(cancel,dict) and cancel.get('cancelState')=='NONE_REQUESTED'
            and cancel.get('cancelRequests')==[]
            and isinstance(value['fulfillmentHrefs'],list))


def observed_subset(observed,detail):
    """Permit authoritative detail to fill absent fields, never change seen ones."""
    if isinstance(observed,dict):
        return isinstance(detail,dict) and all(k in detail and observed_subset(v,detail[k]) for k,v in observed.items())
    if isinstance(observed,list):
        return isinstance(detail,list) and len(observed)==len(detail) and all(
            observed_subset(a,b) for a,b in zip(observed,detail))
    return type(observed) is type(detail) and observed==detail
