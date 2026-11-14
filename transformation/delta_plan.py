"""Deployment-time dbt compiler. Runtime never accepts arbitrary caller SQL."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from transformation.source_config import SOURCES

ROOT=Path(os.environ.get('PROJECT_ROOT',Path(__file__).resolve().parents[1]))
SCHEMAS={'internal_web':'build_delta_web','ebay_sim':'build_delta_ebay','etsy_sim':'build_delta_etsy'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def source_hash():
    # Prune generated trees BEFORE traversal. Filtering rglob results would
    # still enumerate every historical per-batch dbt artifact on a bind mount.
    paths=[]
    for directory,children,files in os.walk(ROOT/'transformations'):
        ignored={'__pycache__','.git'}
        if Path(directory)==ROOT/'transformations':
            ignored.update(('target','logs'))
        children[:]=[name for name in children if name not in ignored]
        paths.extend(Path(directory)/name for name in files if Path(name).suffix in ('.sql','.yml','.yaml'))
    paths += [ROOT/'transformation'/name for name in
              ('delta_plan.py','delta_runtime.py','delta_publish.py','source_config.py','admission.py')]
    return digest({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(paths)})


def mapping_hash(conn,source,mapping):
    versions=['s01-v1','s02-catalog-v1'] if mapping=='local-live-v1' else [mapping]
    return conn.execute('''SELECT encode(sha256(convert_to(coalesce(
        jsonb_agg(to_jsonb(m) ORDER BY mapping_id)::text,'[]'),'UTF8')),'hex')
        FROM config.product_mapping m WHERE source_system=%s AND source_account_id=%s
          AND mapping_version=ANY(%s)''',(source,SOURCES[source][0],versions)).fetchone()[0]


def validate(plan):
    value=dict(plan); identity=value.pop('plan_sha256')
    if digest(value)!=identity or source_hash()!=plan['source_hash']:
        raise ValueError('compiled delta plan/source hash mismatch; compile and bootstrap explicitly')
    source=plan['source']
    if source not in SOURCES or plan['schema']!=SCHEMAS[source]:
        raise ValueError('invalid compiled source/schema')
    if not plan['models'] or not plan['tests']:
        raise ValueError('empty delta model or quality gate')
    for kind in ('models','tests'):
        identities=[node['id'] for node in plan[kind]]
        if len(identities)!=len(set(identities)):
            raise ValueError('duplicate compiled node identity')
    for model in plan['models']:
        if model['relation'] != '"data_platform"."'+plan['schema']+'"."'+model['name']+'"':
            raise ValueError('unexpected candidate relation')
    return plan


def check_model_config(node):
    """Refuse dbt features the deliberately small CTAS runner cannot honor."""
    config=node['config']
    if config['materialized'] not in ('table','view') or config.get('contract',{}).get('enforced'):
        raise ValueError('unsupported delta materialization/contract: '+node['name'])
    if config.get('post-hook'):
        raise ValueError('unsupported delta model post-hook: '+node['name'])
    for hook in config.get('pre-hook',[]):
        if node['name']!='stg_etsy_observations' or hook['sql'].strip()!='{{ populate_etsy_cache() }}':
            raise ValueError('unsupported delta model pre-hook: '+node['name'])


def load(path):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')))


def compile_plan(source,mapping,version,output):
    from transformation.batch import connect
    import yaml
    project=yaml.safe_load((ROOT/'transformations/dbt_project.yml').read_text())
    if project.get('on-run-start') != ["{{ create_canonical_jsonb_function() }}",
            "{{ create_ebay_canonical_function() }}","{{ create_etsy_functions() }}"] or \
            project.get('on-run-end') != ["{{ record_etsy_mapping_exceptions() }}"]:
        raise ValueError('unsupported delta project hooks; extend runner and regression explicitly')
    code_hash=source_hash()
    variables=dict(delta_mode=True,batch_id='00000000-0000-0000-0000-000000000001',
        release_source=source,mapping_version=mapping,transformation_version=version,
        validation_mode='runtime')
    target=Path(tempfile.gettempdir())/'platform-delta-compile'/digest([source,mapping,version,code_hash])
    command=[str(Path(sys.executable).with_name('dbt')),
        '--project-dir',str(ROOT/'transformations'),'--profiles-dir',str(ROOT/'infra/dbt'),
        '--target-path',str(target),'--log-path',str(target/'logs'),'--vars',json.dumps(variables)]
    compiled=subprocess.run([command[0],'compile',*command[1:]],text=True,capture_output=True)
    if compiled.returncode: raise RuntimeError('dbt compile failed: '+compiled.stdout[-5000:]+compiled.stderr[-1000:])
    # run-operation writes a parsed manifest at the same target; retain the
    # compiled graph before exporting hooks or compiled_code would disappear.
    manifest=json.loads((target/'manifest.json').read_text())
    hooks=subprocess.run([command[0],'run-operation','export_delta_hooks',*command[1:]],text=True,capture_output=True)
    if hooks.returncode: raise RuntimeError('dbt hook export failed: '+hooks.stdout[-5000:])
    marker='DELTA_HOOKS_JSON='
    lines=[line.split(marker,1)[1] for line in hooks.stdout.splitlines() if marker in line]
    if len(lines)!=1: raise RuntimeError('missing or ambiguous dbt hook export')
    exported=json.JSONDecoder().raw_decode(lines[0])[0]
    folder={'internal_web':None,'ebay_sim':'ebay','etsy_sim':'etsy'}[source]
    selected={key:n for key,n in manifest['nodes'].items() if n['resource_type']=='model'
              and (('/'+folder+'/' in n['original_file_path']) if folder else
                   n['name'].startswith('candidate_') or n['name'] in ('stg_website_observations','int_website_versions'))}
    ordered=[]; remaining=dict(selected)
    while remaining:
        ready=[(key,n) for key,n in sorted(remaining.items())
               if all(d not in remaining for d in n['depends_on']['nodes'])]
        if not ready: raise ValueError('cyclic delta graph')
        for key,node in ready:
            check_model_config(node)
            external=[d for d in node['depends_on']['nodes'] if d.startswith('model.') and d not in selected]
            if external: raise ValueError('cross-source model dependency: '+key)
            ordered.append(dict(id=key,name=node['name'],relation=node['relation_name'],sql=node['compiled_code']))
            del remaining[key]
    tests=[]
    for key,node in sorted(manifest['nodes'].items()):
        if node['resource_type']!='test' or '_s01' in node['name']: continue
        deps={d for d in node['depends_on']['nodes'] if d.startswith('model.')}
        if (deps and deps<=selected.keys()) or node['name']=='injected_failure':
            config=node['config']
            if str(config.get('severity','ERROR')).upper()!='ERROR' or \
                    config.get('fail_calc','count(*)').replace(' ','')!='count(*)' or \
                    config.get('error_if','!=0').replace(' ','')!='!=0':
                raise ValueError('unsupported delta test policy: '+node['name'])
            tests.append(dict(id=key,sql=node['compiled_code']))
    with connect() as conn: config_hash=mapping_hash(conn,source,mapping)
    plan=dict(format=1,source=source,schema=SCHEMAS[source],mapping_version=mapping,
              transformation_version=version,source_hash=code_hash,mapping_hash=config_hash,
              models=ordered,tests=tests,hooks=exported)
    plan['plan_sha256']=digest(plan); validate(plan)
    if source_hash()!=code_hash: raise ValueError('source changed during compilation')
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: json.dump(plan,stream,indent=2)
    return plan['plan_sha256']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=tuple(SOURCES),required=True)
    parser.add_argument('--mapping-version',default='local-live-v1')
    parser.add_argument('--transformation-version',default='m08d-delta-v1')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(compile_plan(args.source,args.mapping_version,args.transformation_version,args.output))
