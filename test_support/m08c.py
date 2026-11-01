"""Explicit case inventory and guarded recovery tests; never faults the owner stack."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from test_support import m08a as guard

ROOT = guard.ROOT
OFFLINE = ('test_s02_live.py', 'test_m08c.py', 'test_m08c_http.py',
           'test_m05_http.py', 'test_m06_unit.py', 'test_m06_draining.py',
           'test_m06_cycle.py', 'test_m06_scheduling.py')
RUNTIME_SERVICES = ('postgres', 'ebay-sim', 'etsy-sim', 'etsy-receiver')


def inventory():
    return json.loads((ROOT / 'test_support/m08c_cases.json').read_text())


def target(h):
    """Validate config + actual resources + bound DB identity, before case faults."""
    guard.require(h.marker.get('profile', 'm08a') == 'm08a', 'C runner requires accepted A/S01 scope, not B/replay')
    guard.require(h.marker['project'] != guard.OWNER and h.marker['db_system_id'], 'Missing disposable DB identity')
    h.check()
    result = h.root / 'evidence/result.json'
    guard.require(result.is_file(), 'Run M08A baseline acceptance first')
    baseline = json.loads(result.read_text())
    guard.require(baseline.get('status') == 'PASS' and baseline.get('id') == h.marker['id']
                  and baseline.get('test_db_system_id') == h.marker['db_system_id'], 'A baseline did not pass for this identity')
    # Never start a second scheduler, including an already-running retained test one.
    active = h.dc(['ps', '--status', 'running', '--services']).splitlines()
    guard.require(not set(active) - set(RUNTIME_SERVICES), 'Stop test Airflow/observer/report before CLI-only C cases')
    return set(active)


def idle(h):
    h.test_db()
    guard.require(h.sql("SELECT count(*) FROM dag_run WHERE state IN ('running','queued');", 'airflow_meta') == '0',
                  'Test DAG run active; no task clear or forced success allowed')
    guard.require(h.sql("SELECT count(*) FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED');") == '0',
                  'Active/orphaned test batch: inspect and explicitly recover before another case')


def postgres_restart(h):
    tables = (*guard.PROTECTED, 'ops.webhook_inbox', 'ops.webhook_delivery_attempts', 'ops.processing_work')
    signature = h.sql(guard.signature_query(tables))
    identity = h.test_db()
    h.dc(['restart', '--timeout', '30', 'postgres'])
    deadline = time.monotonic() + 60
    while True:
        try:
            guard.require(h.test_db() == identity, 'PostgreSQL identity changed')
            break
        except guard.SafetyError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    guard.require(h.sql(guard.signature_query(tables)) == signature, 'Graceful restart changed durable data')
    return dict(db_system_id=identity, durable_signature_unchanged=True)


def run_case(h, case):
    entries = {entry['id']: entry for entry in inventory()}
    guard.require(case in entries and entries[case]['runner'], 'Case is not implemented; retain NOT_RUN, not PASS')
    initially_running = target(h)
    guard.resource_preflight(h.marker, scheduled=False)
    report = dict(milestone='M08C', case=case, scope=entries[case]['scope'], status='FAIL',
        milestone_complete=False, started_at=guard.utc(), id=h.marker['id'],
        project=h.marker['project'], db_system_id=h.marker['db_system_id'],
        code_sha=guard.execute(['git', 'rev-parse', 'HEAD']),
        dirty_worktree=bool(guard.execute(['git', 'status', '--porcelain'])),
        hashes={name: guard.digest(ROOT / name) for name in (
            'test_support/m08c.py', 'test_support/m08c_pipeline_probe.py', 'test_support/m08c_cases.json',
            'orchestration/polling.py', 'orchestration/website_workflow.py',
            'ingestion/website.py', 'transformation/batch.py', 'transformation/publish.py',
            'test_support/m08c_http_probe.py', 'test_support/m08c_loss_probe.py',
            'test_support/m08c_worker_probe.py', 'test_support/m08c_webhook_probe.py',
            'test_support/m08c_quality_probe.py', 'test_support/m08c_source_worker_probe.py',
            'test_support/m08c_lifecycle.py', 'test_support/airflow/m08c_recovery.py',
            'simulator/http_faults.py', 'simulator/live_worker.py', 'simulator/ebay_api.py', 'simulator/etsy_api.py')})
    # One case per target at a time; a crashed process leaves an explicit latch.
    latch = h.root / 'evidence/m08c.running'
    with latch.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(dict(case=case, started_at=report['started_at'])))
    output = h.root / 'evidence' / ('m08c-' + case + '-' + uuid.uuid4().hex + '.json')
    try:
        h.dc(['up', '--detach', '--wait', '--wait-timeout', '180', *RUNTIME_SERVICES])
        idle(h)
        report['images'] = {service: guard.docker('image','inspect','--format','{{.Id}}',
                            h.model['services'][service]['image']) for service in (*RUNTIME_SERVICES[1:], 'airflow')}
        # DB identity is also different from owner when the owner DB exists.
        owner = guard.docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + guard.OWNER,
                             '--filter', 'label=com.docker.compose.service=postgres')
        if owner:
            guard.require(h.marker['db_system_id'] != guard.owner_sql(owner, 'SELECT system_identifier FROM pg_control_system();', 'postgres'),
                          'Test targets owner PostgreSQL')
        if entries[case]['runner'] == 'restart':
            report['assertions'] = postgres_restart(h)
        elif entries[case]['runner'] == 'lifecycle':
            from test_support.m08c_lifecycle import service_restarts, scheduled_pause_resume, maintenance_drain, task_clear_budget, outage_visibility
            handlers = dict(scheduled_pause_resume=scheduled_pause_resume,
                            maintenance_drain=maintenance_drain, task_clear_budget=task_clear_budget,
                            outage_visibility=outage_visibility)
            report['assertions'] = (handlers[case](h) if case in handlers
                else service_restarts(h, abrupt=(case == 'abrupt_service_loss')))
        else:
            runner = entries[case]['runner']
            if runner == 'pipeline':
                command = ['-m', 'test_support.m08c_pipeline_probe', case]
            elif runner == 'm08c_http_probe':
                command = ['-m', 'test_support.m08c_http_probe']
            elif runner == 'loss':
                command = ['-m', 'test_support.m08c_loss_probe', case]
            elif runner == 'worker':
                command = ['-m', 'test_support.m08c_worker_probe', case]
            elif runner == 'webhook':
                command = ['-m', 'test_support.m08c_webhook_probe']
            elif runner == 'quality':
                command = ['-m', 'test_support.m08c_quality_probe']
            else:
                command = ['/repo/tests/' + runner]
            if case in ('receiver_audit','late_reordered_webhooks','abrupt_raw_inbox'):
                target_command = command[1:] if command[0] == '-m' else command
                command = ['-m', 'test_support.m08c_probe_entry', *target_command]
            # /repo is test-only and read-only; no scheduler is started.
            mounts = [part for name in ('test_support', 'tests', 'fixtures/s01')
                      for part in ('--volume', str(ROOT / name) + ':/repo/' + name + ':ro')]
            if case in ('receiver_audit','late_reordered_webhooks','abrupt_raw_inbox'):
                mounts += ['--volume', str(h.root / 'test.env') + ':/m08c/private.env:ro']
            # Exercise current source, not Python baked into an old accepted image.
            # Keep the application root stable for dbt artifact/profile paths.
            mounts += [part for name in ('orchestration', 'ingestion', 'transformation', 'simulator')
                       for part in ('--volume', str(ROOT / name) + ':/opt/project/' + name + ':ro')]
            # A read-only project root without target/ prevents Docker from
            # creating the nested writable mountpoint. Mount source subtrees,
            # leaving the image's project root and artifact mount independent.
            mounts += [part for name in ('models','macros','tests','dbt_project.yml')
                       for part in ('--volume', str(ROOT / 'transformations' / name)
                                    + ':/opt/project/transformations/' + name + ':ro')]
            mounts += ['--volume', str(h.root / 'binds/dbt') + ':/opt/project/transformations/target']
            result = h.dc(['run', '--rm', '-T', '--no-deps', *mounts,
                '--env', 'PYTHONPATH=/repo:/opt/project', '--entrypoint', '/opt/airflow/project-venv/bin/python',
                'airflow', *command], timeout=900)
            report['probe_summary'] = result.splitlines()[-1] if result else ''
        report['status'] = 'PASS'
    except Exception as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        try:
            started = sorted(set(RUNTIME_SERVICES) - initially_running)
            if entries[case]['runner'] == 'lifecycle':
                started += ['airflow', 'scheduler-observer']
            if started:
                h.dc(['stop', '--timeout', '30', *started])
            report['cleanup'] = 'PASS'
        except Exception as error:
            report.update(status='FAIL', cleanup='FAIL', cleanup_failure=type(error).__name__)
            raise
        finally:
            report.update(finished_at=guard.utc(), steps=h.steps)
            output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            if report.get('cleanup') == 'PASS':
                latch.unlink()
            print('M08C case ' + report['status'] + '; evidence=' + str(output.relative_to(ROOT)), flush=True)
    return report


def offline():
    output = ROOT / 'runtime' / ('m08c-offline-' + uuid.uuid4().hex + '.json')
    output.parent.mkdir(exist_ok=True)
    report = dict(scope='offline component regression, NOT M08C runtime acceptance',
                  started_at=guard.utc(), status='PASS', tests=[])
    for name in OFFLINE:
        env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', ''))
        result = subprocess.run([sys.executable, str(ROOT / 'tests' / name)], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=180)
        count = re.search(r'Ran (\d+) tests?', result.stderr)
        report['tests'].append(dict(file=name, sha256=guard.digest(ROOT / 'tests' / name),
                                   unittest_count=int(count[1]) if count else None,
                                   returncode=result.returncode))
        print(name + ': ' + ('PASS' if result.returncode == 0 else 'FAIL'), flush=True)
        if result.returncode:
            report['status'] = 'FAIL'
            print(result.stdout + result.stderr, file=sys.stderr)
    report['finished_at'] = guard.utc()
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Evidence: ' + str(output.relative_to(ROOT)))
    return 0 if report['status'] == 'PASS' else 1


def evidence_report(identity):
    root = guard.root_for(identity)
    guard.exact_path(root, root)
    summaries = []
    for entry in inventory():
        files = sorted((root / 'evidence').glob('m08c-' + entry['id'] + '-*.json'))
        results = [json.loads(path.read_text()) | {'file': str(path.relative_to(ROOT))} for path in files]
        results.sort(key=lambda row: row.get('finished_at',''))
        last = results[-1] if results else {}
        summaries.append(dict(case=entry['id'], status=last.get('status','NOT_RUN'),
                              evidence=last.get('file'), scope=entry['scope']))
    return dict(id=identity, all_required_cases_passed=all(r['status']=='PASS' for r in summaries),
                note='Check owner restoration, source hashes, limits and affected regressions before milestone sign-off', cases=summaries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'offline', 'run', 'report'))
    parser.add_argument('--id')
    parser.add_argument('--case', choices=[r['id'] for r in inventory()])
    parser.add_argument('--confirm-disposable', action='store_true')
    args = parser.parse_args()
    if args.action == 'plan':
        print(json.dumps(dict(milestone='M08C', milestone_complete=False, cases=[
            dict(**row, evidence_status='NOT_RUN', execution_supported=bool(row['runner']))
            for row in inventory()]), indent=2))
        return 0
    if args.action == 'offline':
        return offline()
    if args.action == 'report':
        guard.require(args.id, 'report requires --id')
        print(json.dumps(evidence_report(args.id), indent=2))
        return 0
    guard.require(args.confirm_disposable and args.id and args.case, 'run requires --id --case --confirm-disposable')
    # Reject unsupported cases before constructing any Docker-backed harness.
    guard.require(next(r for r in inventory() if r['id'] == args.case)['runner'], 'Case not implemented; NOT_RUN')
    run_case(guard.Harness(args.id), args.case)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (guard.SafetyError, FileExistsError) as error:
        print('M08C refused: ' + str(error) + '; no automatic reset', file=sys.stderr)
        sys.exit(1)
