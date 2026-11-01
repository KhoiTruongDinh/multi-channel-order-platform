"""Owner-authorized drain/stop/restore window for a fresh guarded recovery baseline."""
import argparse
import json
import uuid

from test_support import m08a as guard
from test_support.m08b_window import pauses, restore, state
from tools.s02_data.live import drain, DAGS
from tools.s02_data.load import LocalDB


def run(confirmed, cases, identity=None):
    guard.require(confirmed, 'Current owner authorization and confirmation flag required')
    owner = guard.owner_container()
    ids = guard.docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + guard.OWNER,
                       '--filter', 'label=com.docker.compose.service=airflow').split()
    guard.require(len(ids) == 1, 'Exactly one running owner Airflow required')
    airflow = ids[0]
    guard.require(state(airflow).get('Health', {}).get('Status') == 'healthy', 'Owner Airflow unhealthy before window')
    # Check future source plans before any maintenance mutation. Airflow pause is
    # not producer pause and does not grant permission to stop live-source.
    pending = guard.owner_sql(owner, '''SELECT
      (SELECT count(*) FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
       LEFT JOIN s02.live_website_progress p USING(campaign_id,order_id) WHERE v.sequence>coalesce(p.sequence,0))+
      (SELECT count(*) FROM s02.deliveries d JOIN s02.live_batches b USING(campaign_id)
       WHERE NOT omitted AND delivered_at IS NULL);''', 'marketplace_sim')
    guard.require(pending == '0', 'Owner source emissions pending; wait, do not stop producers')
    root = guard.ROOT / 'runtime/isolated' / ('c-window-' + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    report = dict(started_at=guard.utc(), owner_airflow=airflow, owner_postgres=owner,
                  pauses_before=pauses(owner), status='FAIL', stop_attempted=False)
    (root / 'start.json').write_text(json.dumps(report, indent=2))
    try:
        print('M08C draining owner schedules; running/retrying work remains runnable', flush=True)
        drain(LocalDB(), timeout=900)
        guard.owner_idle(owner)
        guard.require(state(airflow).get('Health', {}).get('Status') == 'healthy', 'Owner unhealthy after drain')
        report['protected_before'] = guard.protected_signature(owner)
        report['postgres_system_before'] = guard.owner_sql(owner, 'SELECT system_identifier FROM pg_control_system();', 'postgres')
        report['stop_attempted'] = True
        (root / 'start.json').write_text(json.dumps(report, indent=2))
        guard.docker('stop', '--timeout', '30', airflow)
        identity = identity or guard.init()
        report['test_id'] = identity
        (root / 'start.json').write_text(json.dumps(report, indent=2))
        h = guard.Harness(identity)
        if not (h.root / 'evidence/result.json').is_file():
            guard.accept(h)
        else:
            from test_support.m08c import target
            target(h)
            h.dc(['build','ebay-sim','etsy-sim'], timeout=300)
        from test_support.m08c import run_case
        report['cases'] = []
        for case in cases:
            outcome = run_case(h, case)
            report['cases'].append(dict(case=case, status=outcome['status']))
        report['status'] = 'PASS'
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        try:
            if report['stop_attempted']:
                restore(airflow, timeout=420)
                guard.owner_idle(owner)
                report['protected_after'] = guard.protected_signature(owner)
                guard.require(report['protected_after'] == report['protected_before'], 'Owner signature changed/inconclusive')
                guard.require(guard.owner_sql(owner, 'SELECT system_identifier FROM pg_control_system();', 'postgres')
                              == report['postgres_system_before'], 'Owner PG identity changed')
        except BaseException as error:
            report.update(status='FAIL', protection_failure=type(error).__name__ + ': ' + str(error))
            raise
        # Restore all original pause flags even when drain/baseline fails.
        finally:
            try:
                db = LocalDB()
                db.command(['exec', '-T', 'airflow', 'python', '-c',
                    'from pathlib import Path; Path("/opt/airflow/state/polling-drain").unlink(missing_ok=True)'])
                for row in report['pauses_before']:
                    if row['dag_id'] in DAGS:
                        db.command(['exec', '-T', 'airflow', 'airflow', 'dags',
                                    'pause' if row['is_paused'] else 'unpause', row['dag_id']])
                guard.require(pauses(owner) == report['pauses_before'], 'Owner pause state restoration mismatch')
                report['owner_restore'] = 'PASS'
            except BaseException as error:
                report.update(status='FAIL', owner_restore='FAIL', restore_failure=str(error))
                raise
            finally:
                report['finished_at'] = guard.utc()
                (root / 'result.json').write_text(json.dumps(report, indent=2))
                print('M08C owner window evidence: ' + str(root.relative_to(guard.ROOT)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-owner-airflow-window', action='store_true')
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--id', help='Reuse a current accepted disposable baseline, never adopt an old marker')
    args = parser.parse_args()
    run(args.confirm_owner_airflow_window, args.case, args.id)
