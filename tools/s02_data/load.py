"""Additive DB loading through existing Compose PostgreSQL; no host DB dependency."""
import hashlib
import json
from pathlib import Path
import subprocess

from tools.s02_data.generate import campaign_id, events
from tools.s02_data.config import parse_time
from tools.s02_data.references import references
from test_support.s02_plan import checksum, literal, mapping_sql, prepare_sql

ROOT=Path(__file__).resolve().parents[2]


class LocalDB:
    def __init__(self):
        self.base=['docker','compose','--project-name','multi-channel-order-platform','--env-file',str(ROOT/'.env'),
                   '--file',str(ROOT/'infra/compose.yaml')]

    def command(self,args,body=None,timeout=120):
        result=subprocess.run(self.base+args,input=body,text=True,encoding='utf-8',
            capture_output=True,cwd=ROOT,timeout=timeout)
        if result.returncode:
            # SQL can contain private passwords; do not echo stderr/SQL in exceptions.
            raise RuntimeError('Compose/SQL command failed; inspect target service (secrets suppressed)')
        return result.stdout.strip()

    def sql(self,query,db='marketplace_sim'):
        return self.command(['exec','-T','postgres','psql','-XAt','--set','ON_ERROR_STOP=1',
            '-U','postgres','-d',db],query)

    def model(self):
        return json.loads(self.command(['--profile','*','config','--format','json']))


def query(db,sql,name='marketplace_sim'):
    raw=db.sql("SELECT coalesce(json_agg(t),'[]') FROM ("+sql+") t;",name)
    return json.loads(raw.strip())


def migrations(db):
    for name in ('001_s02_temporal.sql','002_local_playback.sql'):
        db.sql((ROOT/'migrations/marketplace_sim'/name).read_text())


def load_references(db,ref):
    keys=dict(customers='customer_id',products='product_id',product_variants='variant_id')
    statements=['BEGIN;']
    for table,key in keys.items():
        for row in ref[table]:
            values={k:(literal(json.dumps(v))+'::jsonb' if isinstance(v,dict) else
                       'TRUE' if v is True else 'FALSE' if v is False else literal(v)) for k,v in row.items()}
            condition=' OR '.join(k+' IS DISTINCT FROM '+v for k,v in values.items())
            tag='$ref_'+hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()+'$'
            statements.append('DO '+tag+' BEGIN IF EXISTS(SELECT FROM public.'+table+' WHERE '+key+'='+literal(row[key])+
                              ' AND ('+condition+")) THEN RAISE EXCEPTION 'existing S02 reference differs'; END IF; END "+tag+';')
            statements.append('INSERT INTO public.'+table+'('+','.join(values)+') VALUES ('+','.join(values.values())+
                              ') ON CONFLICT ('+key+') DO NOTHING;')
    statements.append('COMMIT;')
    db.sql('\n'.join(statements),'website_source')


def validate_order(batch,config):
    """Source invariants, not warehouse expected outputs."""
    from decimal import Decimal
    previous=None; purchase=None
    for e in batch:
        p=e['payload']; source=e['source']
        if previous is not None and e['visible_at']<=previous: raise ValueError('nonmonotonic source version')
        previous=e['visible_at']
        if source=='internal_web':
            o=p['orders'][0]; lines=p['order_items']
            signature=[(l['order_item_id'],l['variant_id'],l['quantity'],l['unit_price']) for l in lines]
            total=sum(Decimal(l['unit_price'])*l['quantity'] for l in lines)
            if total!=Decimal(o['items_gross_amount']) or total!=Decimal(o['order_total_amount']): raise ValueError('Website money mismatch')
        elif source=='ebay_sim':
            o=p['order']; lines=o['lineItems']
            signature=[(l['lineItemId'],l['sku'],l['quantity'],l['lineItemCost']) for l in lines]
            total=sum(Decimal(l['lineItemCost']['value']) for l in lines)
            if total!=Decimal(o['pricingSummary']['total']['value']): raise ValueError('eBay money mismatch')
            allocated={l['lineItemId']:0 for l in lines}
            for f in p['fulfillments']:
                for l in f['lineItems']: allocated[l['lineItemId']]+=l['quantity']
            if any(allocated[l['lineItemId']]>l['quantity'] for l in lines): raise ValueError('over shipment')
        else:
            lines=p['transactions']
            signature=[(l['transaction_id'],l['sku'],l['quantity'],l['price']) for l in lines]
            total=sum(l['price']['amount']*l['quantity'] for l in lines)
            if total!=p['grandtotal']['amount']: raise ValueError('Etsy money mismatch')
        if any(type(l['quantity']) is not int or l['quantity']<=0 for l in lines): raise ValueError('invalid quantity')
        if purchase is not None and purchase!=signature: raise ValueError('purchase changed across lifecycle')
        purchase=signature


def prepare(db,config):
    """LOADING is retained on error; never overwrite or silently resume/reseed."""
    identity=campaign_id(config['dataset']); ref=references()
    # Validate generation fully before the first write, without retaining the dataset in RAM.
    digest=hashlib.sha256(); totals={s:0 for s in config['channels']}; coverage={s:{} for s in config['channels']}
    for batch in events(config):
        validate_order(batch,config)
        digest.update(json.dumps(batch,sort_keys=True,separators=(',',':')).encode())
        source=batch[0]['source']; branch=batch[0]['case']
        totals[source]=totals.get(source,0)+len(batch)
        coverage.setdefault(source,{})[branch]=coverage.setdefault(source,{}).get(branch,0)+1
    manifest=dict(config=config,source_versions=totals,cases=coverage,reference_checksum=checksum(ref),
        event_checksum=digest.hexdigest(),status='PLANNED_NOT_EXECUTED',
        excluded_faults=['API429/500/timeout/malformed','invalid_signature','crash/restart','missing_mapping'],
        excluded_reason='Not executed by this generator; explicit M08C hooks/cases required')
    migrations(db)
    if query(db,'SELECT id FROM s02.campaigns WHERE id='+literal(identity)):
        raise ValueError('dataset ID already exists; no automatic overwrite/reset')
    db.sql('BEGIN; INSERT INTO s02.campaigns(id,seed,config,checksum) VALUES ('+
        ','.join((literal(identity),str(config['order_seed']),literal(json.dumps(config))+'::jsonb',literal(checksum(manifest))))+');'+
        'INSERT INTO s02.local_datasets VALUES ('+literal(identity)+','+literal(config['dataset'])+
        ",'LOADING',"+literal(json.dumps(ref))+'::jsonb,'+literal(json.dumps(manifest))+'::jsonb); COMMIT;')
    pending=[]
    for batch in events(config):
        value=dict(id=identity,seed=config['order_seed'],events=batch)
        pending.extend(prepare_sql(value).splitlines()[2:-2])
        for e in batch:
            if e['source']=='internal_web':
                pending.append('INSERT INTO s02.website_versions VALUES ('+','.join((literal(identity),literal(e['order_id']),
                    str(e['sequence']),literal(e['visible_at']),literal(json.dumps(e['payload']))+'::jsonb'))+');')
        if len(pending)>300:
            db.sql('BEGIN;\n'+'\n'.join(pending)+'\nCOMMIT;'); pending=[]
    if pending: db.sql('BEGIN;\n'+'\n'.join(pending)+'\nCOMMIT;')
    # Exact-content idempotency: do not silently change owner mappings.
    old_rows={r['mapping_id']:r for r in query(db,"SELECT * FROM config.product_mapping WHERE mapping_version='s02-catalog-v1'",'data_platform')}
    missing=[]
    for row in ref['mapping']:
        old=old_rows.get(row['mapping_id'])
        if old:
            comparable={k:old[k] for k in row if k not in ('valid_from','valid_to','created_at')}
            if comparable!={k:v for k,v in row.items() if k not in ('valid_from','valid_to','created_at')}:
                raise ValueError('existing mapping differs; dataset remains LOADING')
            if old['valid_to'] is not None or any(parse_time(old[k])!=parse_time(row[k]) for k in ('valid_from','created_at')):
                raise ValueError('existing mapping validity differs; dataset remains LOADING')
        else: missing.append(row)
    if missing: db.sql(mapping_sql(dict(references=dict(mapping=missing))),'data_platform')
    load_references(db,ref)
    db.sql('BEGIN; UPDATE s02.campaigns SET sealed=TRUE WHERE id='+literal(identity)+';'+
        "UPDATE s02.local_datasets SET state='READY' WHERE campaign_id="+literal(identity)+'; COMMIT;')
    return dict(dataset=config['dataset'],campaign_id=identity,manifest=manifest)


def inspect(db,name):
    return query(db,'SELECT name,campaign_id,state,coverage FROM s02.local_datasets WHERE name='+literal(name))


def admit_live(db,name):
    """Publish complete source-only data to the running live sources atomically."""
    db.sql((ROOT/'migrations/marketplace_sim/003_live_batches.sql').read_text())
    # Serializes identity checks with all other live admissions. No pipeline state
    # is changed; timestamps advance from actual admission, never old checkpoints.
    sql='''BEGIN;
      SELECT pg_advisory_xact_lock(hashtext('live-source-admission'));
      INSERT INTO s02.live_batches(campaign_id,published_at,shift_seconds)
      SELECT d.campaign_id,statement_timestamp(),
             ceil(extract(epoch FROM statement_timestamp()-min((ch.value->>'start_at')::timestamptz)))::bigint+2
      FROM s02.local_datasets d JOIN s02.campaigns c ON c.id=d.campaign_id,
           jsonb_each(c.config->'channels') ch
      WHERE d.name='''+literal(name)+''' AND d.state='READY' AND c.sealed
      GROUP BY d.campaign_id;
      COMMIT;'''
    db.sql(sql)
    rows=query(db,'SELECT b.* FROM s02.live_batches b JOIN s02.local_datasets d USING(campaign_id) WHERE d.name='+literal(name))
    if not rows: raise ValueError('READY dataset required for live admission')
    return dict(dataset=name,status='LIVE',admission=rows[0],
        note='Live APIs/worker discover this batch automatically; no DAG trigger or campaign switch')
