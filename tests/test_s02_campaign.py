"""Observation campaign guards, timeline and restoration; no Docker runtime claim."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.s02_data import campaign as c
from tools.s02_data.campaign_config import validate_campaign,timeline
from tools.s02_data.config import validate
from tools.s02_data.generate import events

ROOT=Path(__file__).resolve().parents[1]


class CampaignTests(unittest.TestCase):
    def config(self,mode='normal'):
        value=json.loads((ROOT/f'tools/s02_data/config/campaign_{mode}.json').read_text())
        value.update(start_at='2026-11-06T00:00:00Z',end_at='2026-11-06T00:02:00Z')
        return validate(value)

    def test_seeded_window_and_invalid_options(self):
        s=self.config('recovery')['campaign']; event=timeline(s)
        self.assertEqual(event,timeline(s))
        low,high=s['fault']['start_window_seconds']
        self.assertTrue(low<=event['start_after_seconds']<=high)
        for value in ({'unknown':1},{'poll_seconds':True},{'fault':{'kind':'delete_volume'}},
                      {'fault':{'kind':'ebay_pause','duration_seconds':300}},
                      {'timeout_seconds':30,'fault':{'kind':'ebay_pause'}}):
            with self.subTest(value=value),self.assertRaises(ValueError): validate_campaign(value)

    def test_campaign_config_does_not_change_generated_data(self):
        value=self.config('recovery'); plain=copy.deepcopy(value); plain.pop('campaign')
        self.assertEqual(list(events(value)),list(events(plain)))

    def test_consent_before_runtime_or_db_calls(self):
        db=Mock()
        with self.assertRaisesRegex(ValueError,'confirm-local'): c.run(db,self.config())
        with self.assertRaisesRegex(ValueError,'allow-faults'): c.run(db,self.config('recovery'),True)
        db.assert_not_called(); db.model.assert_not_called()

    def test_restore_never_unpauses_replacement_or_foreign_target(self):
        db=Mock(); target=dict(project=c.PROJECT,service='ebay-sim',id='a'*64)
        with patch.object(c,'service',return_value=dict(ID='b'*64,State='paused')),patch.object(c,'compose') as command:
            with self.assertRaisesRegex(ValueError,'changed'): c.restore_fault(db,target)
        command.assert_not_called()
        target['service']='postgres'
        with self.assertRaisesRegex(ValueError,'invalid'): c.restore_fault(db,target)

    def test_restore_same_paused_container_only(self):
        target=dict(project=c.PROJECT,service='ebay-sim',id='a'*64)
        with patch.object(c,'service',side_effect=[dict(ID='a'*64,State='paused'),dict(ID='a'*64,State='running')]), \
             patch.object(c,'compose') as command:
            self.assertEqual(c.restore_fault(Mock(),target),'RESTORED')
        self.assertEqual(command.call_args.args[1],['unpause','ebay-sim'])

    def test_docker_paused_flag_overrides_running_status(self):
        db=Mock(); db.command.return_value=json.dumps(dict(ID='a'*64,State='running'))
        actual=[dict(Config=dict(Labels={'com.docker.compose.project':c.PROJECT,'com.docker.compose.service':'ebay-sim'}),
                     State=dict(Paused=True,Status='running'))]
        with patch.object(c.subprocess,'run',return_value=Mock(stdout=json.dumps(actual))):
            self.assertEqual(c.service(db,'ebay-sim')['State'],'paused')

    def test_restore_requires_local_consent_and_runtime_path(self):
        with self.assertRaisesRegex(ValueError,'confirm-local'): c.restore(Mock(),Path('unused'))
        with self.assertRaisesRegex(ValueError,'runtime'): c.restore(Mock(),ROOT/'README.md',True)

    def test_orphaned_build_requires_operator_not_automatic_abort(self):
        batch=dict(batch_id='old-batch',airflow_dag_id='ebay_polling',airflow_run_id='old-run')
        db=Mock()
        with patch.object(c,'query',side_effect=[[batch],[dict(state='failed')],[batch]]):
            with self.assertRaisesRegex(ValueError,'operator recovery.*old-batch'): c.require_no_orphaned_release(db)
        db.sql.assert_not_called()

    def test_guard_rechecks_barrier_after_owner_becomes_terminal(self):
        batch=dict(batch_id='old-batch',airflow_dag_id='ebay_polling',airflow_run_id='old-run')
        db=Mock()
        with patch.object(c,'query',side_effect=[[batch],[dict(state='success')],[]]) as query:
            c.require_no_orphaned_release(db)
        self.assertEqual(query.call_count,3)
        db.sql.assert_not_called()

    def test_guard_rechecks_late_owner_but_still_refuses_true_orphan(self):
        original=dict(batch_id='old-batch',airflow_dag_id=None,airflow_run_id=None)
        annotated=dict(original,airflow_dag_id='website_polling',airflow_run_id='real-run')
        for state in ('running','failed'):
            db=Mock()
            with patch.object(c,'query',side_effect=[[original],[annotated],[dict(state=state)]]):
                if state=='running':
                    c.require_no_orphaned_release(db)
                else:
                    with self.assertRaisesRegex(ValueError,'operator recovery'):
                        c.require_no_orphaned_release(db)
            db.sql.assert_not_called()

    def test_drain_guard_refuses_before_schedule_mutation(self):
        from tools.s02_data.live import _drain_schedules
        db=Mock(); guard=Mock(side_effect=ValueError('operator recovery required'))
        with self.assertRaisesRegex(ValueError,'operator recovery'):
            _drain_schedules(db,10,['website_polling'],guard)
        db.command.assert_not_called(); db.sql.assert_not_called()

    def test_drain_rechecks_owner_after_restart_not_only_initial_preflight(self):
        from tools.s02_data import live
        db=Mock(); guard=Mock(side_effect=[None,ValueError('owner became terminal')])
        with patch.object(live,'query',side_effect=[[],[]]),self.assertRaisesRegex(ValueError,'terminal'):
            live._drain_schedules(db,10,[],guard)
        self.assertEqual(guard.call_count,2)

    def fake_run(self,error=None,fault=False,measurement=False,measurement_error=None):
        db=Mock(); db.model.return_value=dict(name=c.PROJECT,services={'airflow':{},'report':{},'postgres':{}})
        config=self.config('recovery' if fault else 'normal')
        monitor=Mock(value={'status':'OBSERVING'})
        monitor.finish.return_value='BASELINE_PASS'
        if measurement: config['campaign']['measurement']={}
        if measurement_error: monitor.finish.side_effect=measurement_error
        def measured(db,config,limits,report):
            report['measurement']=monitor.value
            return monitor
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(c,'ROOT',Path(tmp)),patch.object(c,'startup_lock',return_value=nullcontext()), \
             patch.object(c,'no_disposable_services'), \
             patch.object(c,'service',return_value=dict(ID='a'*64,State='running')) as state, \
             patch.object(c,'resume_retained_airflow'),patch.object(c,'up'),patch.object(c,'require_live'), \
             patch.object(c,'require_no_orphaned_release'), \
             patch.object(c,'prepare',return_value=dict(campaign_id='abcdef123456',manifest={})), \
             patch.object(c,'admit_live',return_value={}),patch.object(c,'expected_orders',return_value=[{}]), \
             patch.object(c,'compose'),patch.object(c,'restore_fault',return_value='RESTORED') as restore, \
             patch.object(c,'timeline',return_value=dict(start_after_seconds=0,duration_seconds=15) if fault else None), \
             patch('test_support.m08d_measure.Monitor',side_effect=measured), \
             patch.object(c,'snapshot',side_effect=error,return_value=dict(reached_final_versions=True)):
            if fault: state.side_effect=[dict(ID='a'*64,State='running'),dict(ID='a'*64,State='running'),dict(ID='a'*64,State='paused')]
            if error or measurement_error:
                with self.assertRaises(type(error or measurement_error)): c.run(db,config,True,fault)
            else: c.run(db,config,True,fault)
            if measurement:
                monitor.before_prepare.assert_called_once()
                monitor.sample.assert_called_once()
                monitor.admitted.assert_called_once_with('abcdef123456')
                monitor.observe.assert_called_once()
                monitor.finish.assert_called_once()
            report=json.loads(next((Path(tmp)/'runtime').glob('*/report.json')).read_text())
            return report,restore.call_count

    def test_normal_finishes_for_review_not_performance_pass(self):
        report,calls=self.fake_run()
        self.assertEqual(report['status'],'READY_FOR_REVIEW')
        self.assertEqual(report['performance_assessment'],'DEFERRED'); self.assertEqual(calls,0)

    def test_opt_in_measurement_runs_and_cannot_hide_failed_verdict(self):
        report,_=self.fake_run(measurement=True)
        self.assertEqual(report['performance_assessment'],'BOUNDED_BASELINE_NOT_FULL_M08D')
        self.assertIn('BASELINE_RESULT',[r['event'] for r in report['events']])
        report,_=self.fake_run(measurement=True,measurement_error=RuntimeError('reconciliation failed'))
        self.assertEqual(report['status'],'FAILED')
        self.assertNotIn('READY_FOR_REVIEW',[r['event'] for r in report['events']])

    def test_measurement_freezes_dbt_plan_and_release_code(self):
        import hashlib
        report,_=self.fake_run(measurement=True)
        root=Path(c.__file__).resolve().parents[2]
        for name in ('transformations/dbt_project.yml','transformations/models/intermediate/int_website_versions.sql',
                     'transformations/models/schema.yml','transformations/macros/canonical_jsonb.sql',
                     'transformations/tests/website_constraints.sql','transformation/publish.py',
                     'ingestion/pagination.py','ingestion/ebay.py'):
            self.assertEqual(report['hashes'][name],hashlib.sha256((root/name).read_bytes()).hexdigest())
        self.assertFalse(any('/target/' in name for name in report['hashes']))

    def test_plan_ceiling_refuses_before_docker_or_preparation(self):
        from test_support.m08d_measure import SafetyCeiling
        config=self.config(); config['campaign']['measurement']={}
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'ROOT',Path(tmp)), \
             patch('test_support.m08d_measure.Monitor',side_effect=SafetyCeiling('finite plan')), \
             patch.object(c,'no_disposable_services') as discovery,patch.object(c,'prepare') as prepare:
            with self.assertRaises(SafetyCeiling): c.run(Mock(),config,True)
        discovery.assert_not_called(); prepare.assert_not_called()

    def test_error_and_interrupt_restore_campaign_fault(self):
        for error in (ValueError('read failed'),KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                report,calls=self.fake_run(error,True)
                self.assertEqual(calls,1); self.assertEqual(report['fault_cleanup'],'RESTORED')
                self.assertFalse(report['fault_active'])
                self.assertIn(report['status'],('FAILED','INTERRUPTED'))

    def test_outage_restores_before_review_and_does_not_score_performance(self):
        with patch.object(c.time,'monotonic',side_effect=iter(range(0,1000,10))), \
             patch.object(c.time,'sleep'):
            report,calls=self.fake_run(fault=True)
        self.assertEqual(calls,1)
        self.assertEqual(report['status'],'READY_FOR_REVIEW')
        self.assertEqual(report['fault_cleanup'],'RESTORED')
        self.assertEqual(report['performance_assessment'],'DEFERRED')
        self.assertFalse(report['fault_active'])
        self.assertIn('OUTAGE_RESTORED',[row['event'] for row in report['events']])


if __name__=='__main__': unittest.main(verbosity=2)
