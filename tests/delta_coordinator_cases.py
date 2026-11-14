"""Real PostgreSQL/compiled-dbt coordinator cases; collector is a test double."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import sys
import uuid
from unittest.mock import patch


def check(plans,acquire,admin,fixture):
    import json
    from orchestration import polling,coordinator,website_workflow as w
    from transformation.batch import connect,freeze as legacy_freeze,main as batch_main
    checks=[]

    def args(name,source='internal_web',**overrides):
        a=argparse.Namespace(source=source,execution_id='delta-coordinator:'+name,dag_id='delta_probe',
            airflow_run_id='scheduled__'+name,window_end=datetime(2026,10,17,10,1,tzinfo=timezone.utc),
            initial_start=datetime(2026,10,17,tzinfo=timezone.utc),mapping_version='s01-v1',
            transformation_version='legacy',overlap_seconds=0,wait_seconds=60,nonblocking=True,
            reuse_cycle_config=True,abort=False,coordinator_attempt=1,page_size=50,
            fault_after_raw_once=False,fault_after_freeze_once=False,inject_test_failure=False,
            collection_mode='recovery',checkpoint_stream=None)
        for key,value in overrides.items(): setattr(a,key,value)
        polling.prepare(a)
        return a

    def run(a):
        def command(module,*argv):
            if module.startswith('ingestion.'):
                if a.source=='internal_web':
                    payload=json.loads((fixture/'internal_web/WEB_R1.json').read_text())
                    _,run_id=acquire(a.source,payload,'website_order_window')
                elif a.source=='ebay_sim':
                    payload=json.loads((fixture/'ebay_sim/EB_R2.json').read_text())['orders'][0]
                    raw,run_id=acquire(a.source,payload,'ebay_order')
                    acquire(a.source,json.loads((fixture/'ebay_sim/EB_F1.json').read_text()),
                            'ebay_fulfillments',{'order_raw_id':str(raw)},run_id)
                else:
                    _,run_id=acquire(a.source,json.loads((fixture/'etsy_sim/ET_R1.json').read_text()),'etsy_receipt')
                with admin() as conn:
                    conn.execute('UPDATE ops.pipeline_runs SET log_reference=%s WHERE run_id=%s',
                                 (w.child_locator(a),run_id))
            elif module=='transformation.batch':
                with patch.object(sys,'argv',['batch',*map(str,argv)]): batch_main()
            else:
                raise AssertionError('unexpected subprocess: '+module)
        with patch.object(w,'command',side_effect=command): coordinator.coordinate(a)

    directory=str(Path('/tmp/delta-plans'))
    with patch.dict(os.environ,{'POLLING_DELTA_PLAN_DIR':directory}):
        first=args('freeze-interrupted',fault_after_freeze_once=True)
        try: run(first)
        except RuntimeError as error: assert 'intentional interruption' in str(error)
        else: raise AssertionError('freeze injection did not happen')
        with connect() as conn:
            row=conn.execute('''SELECT p.airflow_dag_id,p.airflow_run_id FROM ops.transform_batches b
                JOIN ops.pipeline_runs p ON p.run_id=b.run_id WHERE b.batch_id=%s''',(first.batch_id,)).fetchone()
            assert row==(first.dag_id,first.airflow_run_id)
            count=conn.execute('SELECT count(*) FROM ops.batch_inputs WHERE batch_id=%s',(first.batch_id,)).fetchone()[0]
        # A manual freeze cannot race the retained live owner.
        try:
            legacy_freeze(argparse.Namespace(source='internal_web',batch_id=uuid.uuid4(),run_id=uuid.uuid4(),
                mapping_version='s01-v1',transformation_version='probe',validation_mode='runtime'))
        except RuntimeError as error: assert 'source owner' in str(error)
        else: raise AssertionError('manual freeze bypassed live owner')
        peer=args('blocked-peer')
        try: run(peer)
        except coordinator.CoordinatorBusy: pass
        else: raise AssertionError('peer overtook interrupted owner')
        # A different source runs despite frozen Web and the legacy global slot.
        with connect() as legacy_slot:
            legacy_slot.execute("SELECT pg_advisory_lock(hashtext('platform-release'))"); legacy_slot.commit()
            independent=args('independent-ebay','ebay_sim')
            run(independent)
        resumed=args('freeze-interrupted',fault_after_freeze_once=True)
        run(resumed)
        with connect() as conn:
            assert conn.execute('SELECT count(*) FROM ops.batch_inputs WHERE batch_id=%s',(first.batch_id,)).fetchone()[0]==count
            assert conn.execute("SELECT count(*) FROM ops.task_attempts WHERE run_id=%s AND task_name='collect'",(first.workflow_id,)).fetchone()[0]==1
            assert conn.execute("SELECT status FROM ops.pipeline_runs WHERE batch_id=%s AND stage='PUBLISH'",(first.batch_id,)).fetchone()[0]=='SUCCEEDED'
            assert conn.execute("SELECT count(*) FROM ops.coordinator_waits WHERE run_id=%s AND wait_kind='release_slot'",(first.workflow_id,)).fetchone()[0]==0
        run(peer)
        checks.extend(['actual-Airflow-owner-at-freeze','manual-admission-refuses-live-owner',
                       'same-source-reschedule-no-overtaking','independent-source-no-global-build-wait',
                       'frozen-input-reentry-no-recollection','atomic-publish-audit'])
        # Durable five-attempt gate cannot be reset by another coordinator poke.
        rejected=args('five-gate-failures',inject_test_failure=True)
        for _ in range(5):
            try: run(rejected)
            except RuntimeError as error: assert 'quality gate' in str(error)
            else: raise AssertionError('injected gate unexpectedly passed')
        rejected.inject_test_failure=False
        try: run(rejected)
        except w.AttemptBudgetExhausted: pass
        else: raise AssertionError('attempt budget reset')
        # Missing deployment artifacts must not prevent explicit operator abort.
        rejected.abort=True
        rejected.delta_plan=None
        run(rejected)
        with connect() as conn:
            assert conn.execute('SELECT status FROM ops.transform_batches WHERE batch_id=%s',(rejected.batch_id,)).fetchone()[0]=='FAILED'
        checks.extend(['durable-five-attempt-budget','official-abort-without-plan-file'])
        run(args('post-abort-successor'))
        checks.append('aborted-owner-handoff-without-raw-loss')
        # Old cycles keep the legacy mode even after deployment option changes.
        with patch.dict(os.environ,{'POLLING_DELTA_PLAN_DIR':''}):
            old=args('retained-legacy-cycle')
        old=args('retained-legacy-cycle')
        assert old.delta_plan is None and old.delta_plan_sha256 is None
        checks.append('legacy-cycle-does-not-switch-on-retry')
        with patch.dict(os.environ,{'POLLING_DELTA_PLAN_DIR':''}):
            completed=args('freeze-interrupted',fault_after_freeze_once=True)
            assert completed.delta_plan is None and completed.delta_plan_sha256
            run(completed)
        checks.append('published-cycle-reentry-without-deployment-file')
        pending=args('missing-pinned-plan')
        with patch.dict(os.environ,{'POLLING_DELTA_PLAN_DIR':''}):
            try: args('missing-pinned-plan')
            except ValueError as error: assert 'unavailable' in str(error)
            else: raise AssertionError('missing plan fell back to legacy')
            aborted=args('missing-pinned-plan',abort=True)
            run(aborted)
        checks.append('missing-pinned-plan-refuses-before-collection; explicit-abort-remains-available')
        from transformation.delta_runtime import source_lock,freeze,build
        from transformation.delta_publish import audited_publish
        raw,_=acquire('internal_web',json.loads((fixture/'internal_web/WEB_R1.json').read_text()),'website_order_window')
        plan=plans['internal_web']; batch=uuid.uuid4(); transform=uuid.uuid4(); failed_pub=uuid.uuid4(); good_pub=uuid.uuid4()
        with source_lock(plan) as conn:
            freeze(conn,plan,batch,transform)
            build(conn,plan,batch)
            try: audited_publish(plan,batch,failed_pub,inject_failure=True)
            except RuntimeError: pass
            else: raise AssertionError('publication injection did not happen')
            assert conn.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s',(failed_pub,)).fetchone()[0]=='FAILED'
            assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE raw_record_id=%s',(raw,)).fetchone()[0]==0
            conn.commit()
            audited_publish(plan,batch,good_pub)
            assert conn.execute('SELECT status FROM ops.pipeline_runs WHERE run_id=%s',(good_pub,)).fetchone()[0]=='SUCCEEDED'
        checks.append('failed-publication-audit-and-unconsumed-raw; new-attempt-atomic-success')
    return dict(status='PASS',scope='real coordinator/dbt/SQL; collector test-double, not SLA',checks=checks)
