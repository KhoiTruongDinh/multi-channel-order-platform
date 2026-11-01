"""Manual-only S02 source preparation and local playback commands."""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

from tools.s02_data.config import validate
from tools.s02_data.load import LocalDB,inspect,prepare,query,admit_live


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    gen=sub.add_parser('prepare'); gen.add_argument('--config',type=Path,required=True)
    live=sub.add_parser('generate'); live.add_argument('--config',type=Path,required=True)
    info=sub.add_parser('inspect'); info.add_argument('--dataset',required=True)
    sub.add_parser('status'); sub.add_parser('stop'); sub.add_parser('resume')
    sub.add_parser('live-up')
    sub.add_parser('live-status')
    start=sub.add_parser('start'); start.add_argument('--dataset',required=True)
    start.add_argument('--mode',choices=('realtime','replay'),required=True)
    start.add_argument('--at'); start.add_argument('--confirm-local',action='store_true')
    sub.add_parser('tick')
    play=sub.add_parser('play'); play.add_argument('--interval-seconds',type=int,default=5)
    args=p.parse_args(); db=LocalDB()
    if args.action=='live-up':
        from tools.s02_data.live import up,startup_lock
        with startup_lock(): result=up(db)
    elif args.action=='live-status':
        from tools.s02_data.live import require_live
        require_live(db)
        result=dict(mode='live-pg',pipeline_clock='actual UTC',batches=query(db,'''SELECT d.name,b.* FROM s02.live_batches b
            JOIN s02.local_datasets d USING(campaign_id) ORDER BY published_at'''),
            source_due=query(db,'''SELECT source,count(DISTINCT order_id) AS due_orders FROM (
              SELECT v.source,v.order_id FROM s02.versions v JOIN s02.live_batches b USING(campaign_id)
              WHERE v.visible_at+make_interval(secs=>b.shift_seconds::double precision)<=statement_timestamp()
              UNION ALL SELECT 'internal_web',v.order_id FROM s02.website_versions v
              JOIN s02.live_batches b USING(campaign_id)
              WHERE v.visible_at+make_interval(secs=>b.shift_seconds::double precision)<=statement_timestamp()
            ) due GROUP BY source'''),
            orders=query(db,'SELECT source_system,count(*) FROM core.orders_current GROUP BY source_system','data_platform'))
    elif args.action in ('prepare','generate'):
        # Validate before Docker/DDL. Actual prepare includes complete preflight generation.
        config=validate(json.loads(args.config.read_text(encoding='utf-8')))
        if args.action=='generate':
            from tools.s02_data.live import require_live_storage
            require_live_storage(db)
            # The configured dataset is a readable prefix, not a source selector.
            # Repeated manual executions append new orders without JSON edits.
            config['dataset']=config['dataset'][:48]+'-'+uuid.uuid4().hex[:12]
        result=prepare(db,config)
        if args.action=='generate': result['live']=admit_live(db,config['dataset'])
    elif args.action=='inspect': result=inspect(db,args.dataset)
    elif args.action=='status':
        m=db.model()
        result=dict(project=m['name'],postgres_ports=m['services']['postgres']['ports'],
                    clock=query(db,'SELECT * FROM s02.playback_clock'))
    else:
        from tools.s02_data.playback import activate,stop,resume,tick
        if args.action=='start': result=activate(db,args.dataset,args.mode,args.at,args.confirm_local)
        elif args.action=='stop': result=stop(db)
        elif args.action=='resume': result=resume(db)
        elif args.action=='tick': result=dict(running=tick(db))
        else:
            if not 1<=args.interval_seconds<=60: raise ValueError('play interval must be1..60s')
            while tick(db): time.sleep(args.interval_seconds)
            result=dict(status='playback stopped')
    print(json.dumps(result,indent=2,default=str))


if __name__=='__main__':
    try: main()
    except (ValueError,RuntimeError,OSError) as error:
        print('S02 refused/failed: '+str(error),file=sys.stderr); sys.exit(1)
    except KeyboardInterrupt:
        print('Driver interrupted; clock/services NOT stopped. Use the explicit stop command.',file=sys.stderr)
        sys.exit(130)
