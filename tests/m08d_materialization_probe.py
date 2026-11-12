"""Controlled compiled-SQL parity, temp relations only; main must be drained."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from transformation.batch import connect


def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest',required=True); args=p.parse_args()
    manifest=json.loads(Path(args.manifest).read_text())
    nodes=manifest['nodes']; prefix='model.multi_channel_orders.'
    names=['stg_website_observations','int_website_versions','candidate_order_snapshot_history',
           'candidate_order_line_snapshot_history','candidate_snapshot_evidence']
    selected={name:nodes[prefix+name] for name in names}
    for node in selected.values():
        assert node['compiled_code'].lstrip().upper().startswith(('SELECT','WITH'))
    c=connect()
    try:
        assert c.execute("SELECT pg_try_advisory_lock(hashtext('platform-release'))").fetchone()[0], 'release busy'
        assert not c.execute("SELECT 1 FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED')").fetchone(), 'active batch'
        relations={n:selected[n]['relation_name'] for n in names[:2]}
        sqls={n:selected[n]['compiled_code'].strip().rstrip(';') for n in names}
        result={'scope':'temporary SQL graphs, NOT runtime capacity','manifest_sha256':hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
                'dbt_invocation_id':manifest['metadata']['invocation_id'],'variants':{}}
        for variant,kind in [('views','VIEW'),('tables','TABLE')]:
            replacements={rel:'pg_temp."bench_'+variant+'_'+n+'"' for n,rel in relations.items()}
            def rewrite(sql):
                for original,replacement in replacements.items(): sql=sql.replace(original,replacement)
                return sql
            started=time.monotonic()
            for name in names[:2]:
                c.execute('CREATE TEMP '+kind+' "bench_'+variant+'_'+name+'" AS '+rewrite(sqls[name]))
            prepared=time.monotonic()-started; rows={}
            for name in names[2:]:
                began=time.monotonic()
                c.execute('CREATE TEMP TABLE "out_'+variant+'_'+name+'" AS '+rewrite(sqls[name]))
                elapsed=time.monotonic()-began
                rows[name]={'rows':c.execute('SELECT count(*) FROM "out_'+variant+'_'+name+'"').fetchone()[0],'seconds':elapsed}
            result['variants'][variant]={'preparation_seconds':prepared,'outputs':rows,'total_seconds':time.monotonic()-started}
            print(json.dumps({'variant':variant,**result['variants'][variant]}),flush=True)
        for name in names[2:]:
            differences=c.execute('''SELECT EXISTS((SELECT * FROM "out_views_'''+name+'''" EXCEPT ALL SELECT * FROM "out_tables_'''+name+'''")
              UNION ALL (SELECT * FROM "out_tables_'''+name+'''" EXCEPT ALL SELECT * FROM "out_views_'''+name+'''"))''').fetchone()[0]
            assert not differences,'multiset mismatch: '+name
        result['status']='PASS'; result['comparisons']=names[2:]
        print(json.dumps(result),flush=True)
    finally:
        c.rollback(); c.close()


if __name__=='__main__': main()
