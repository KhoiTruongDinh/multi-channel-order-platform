"""Live source unit/localhost HTTP tests; no Docker or warehouse runtime claims."""
import copy
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer
import json
import io
import os
from pathlib import Path
import sys
import threading
import tempfile
import unittest
from unittest.mock import MagicMock,Mock,patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from simulator.live_source import translate
from simulator.s02_temporal import LivePostgresStore,PostgresStore,make_store,split_document
from tools.s02_data.config import validate,parse_time
from tools.s02_data.generate import events
from tools.s02_data.load import admit_live,validate_order
from tools.s02_data.live import require_live,require_live_storage,up,drain,DAGS,startup_lock,probe_sources
from tools.s02_data import __main__ as cli
from simulator import ebay_api,etsy_api
from test_support import m08a as guard
from orchestration.live_window import bounds
from test_support.m08b_live_check import reread

ROOT=Path(__file__).resolve().parents[1]


def workload():
    value=json.loads((ROOT/'tests/fixtures/s02_quick.json').read_text())
    value.update(start_at='2026-11-01T00:00:00Z',end_at='2026-11-01T00:06:00Z')
    return validate(value)


class LiveTests(unittest.TestCase):
    def test_reread_polls_schedule_counts_then_checks_sources_once(self):
        before=dict(status='PASS',batches=1,scheduled=[dict(dag_id=d,state='success',n=1) for d in DAGS])
        after=dict(status='PASS',batches=1,scheduled=[dict(dag_id=d,state='success',n=2) for d in DAGS])
        with (
            patch('test_support.m08b_live_check.signature',side_effect=[['stable'],['stable']]),
            patch('test_support.m08b_live_check.rows',side_effect=[
                [dict(n=10)],[dict(first_admission='2026-11-01T00:00:00Z')],after['scheduled'],[dict(n=11)]]),
            patch('test_support.m08b_live_check.check',return_value=after) as full_check
        ):
            result=reread(Mock(),before,600)
        full_check.assert_called_once()
        self.assertEqual(result['natural_reread'],dict(status='PASS',raw_before=10,raw_after=11,logical_signature_unchanged=True))

    def test_new_live_cycle_uses_actual_start_not_old_schedule(self):
        now=datetime(2026,11,1,5,tzinfo=timezone.utc)
        end,policy=bounds(None,now)
        self.assertEqual(end,now)
        self.assertEqual(policy,'acquisition-start')

    def test_live_retry_preserves_original_bound_and_policy(self):
        original=datetime(2026,11,1,4,tzinfo=timezone.utc)
        self.assertEqual(bounds((original,{'window_policy':'acquisition-start'}),original+timedelta(hours=1)),
                         (original,'acquisition-start'))
        self.assertEqual(bounds((original,{})),(original,None))
        self.assertEqual(bounds((None,{})),(None,None))
    def test_shift_preserves_business_facts_and_all_three_causal_flows(self):
        c=workload()
        for batch in events(c):
            before=copy.deepcopy(batch)
            after=copy.deepcopy(batch)
            for event in after:
                event['payload']=translate(event['payload'],86400)
                event['visible_at']=(parse_time(event['visible_at'])+timedelta(days=1)).isoformat()
            validate_order(after,c)
            self.assertEqual(batch,before)
            for a,b in zip(batch,after):
                self.assertEqual(a['order_id'],b['order_id'])
                self.assertEqual(parse_time(b['visible_at'])-parse_time(a['visible_at']),timedelta(days=1))

    def test_shift_only_contract_timestamps_not_null_or_arbitrary_values(self):
        value=dict(created_at='2026-11-01T00:00:00Z',resolved_at=None,
            note='2026-11-01T00:00:00Z',created_timestamp=10,quantity=3)
        shifted=translate(value,60)
        self.assertEqual(shifted['created_at'],'2026-11-01T00:01:00+00:00')
        self.assertEqual(shifted['created_timestamp'],70)
        self.assertIsNone(shifted['resolved_at'])
        self.assertEqual(shifted['note'],value['note'])
        self.assertEqual(shifted['quantity'],3)

    def test_live_store_needs_no_campaign_and_s01_default_unchanged(self):
        with patch.dict(os.environ,{'SIMULATOR_MODE':'live-pg'},clear=True):
            self.assertIsInstance(make_store('ebay'),LivePostgresStore)
            self.assertIsInstance(make_store('etsy'),LivePostgresStore)
        with patch.dict(os.environ,{},clear=True): self.assertIsNone(make_store('ebay'))

    def test_live_query_snapshot_window_and_pagination(self):
        doc=next(b[0]['payload'] for b in events(workload()) if b[0]['source']=='ebay_sim')
        base,header,components=split_document('ebay_sim',doc)
        cursor=MagicMock()
        cursor.fetchone.side_effect=[(datetime.now(timezone.utc),),(1,)]
        cursor.fetchall.return_value=[(base,header,components,60)]
        conn=MagicMock(); conn.__enter__.return_value=conn
        conn.cursor.return_value.__enter__.return_value=cursor
        rows,total=LivePostgresStore('ebay',connect=lambda:conn).query(limit=1,offset=0)
        self.assertEqual(total,1)
        self.assertEqual(rows,[translate(doc,60)])
        calls=cursor.execute.call_args_list
        self.assertIn('REPEATABLE READ',calls[0].args[0])
        self.assertIn('s02.live_batches',calls[2].args[0])
        self.assertIn('effective_updated',calls[2].args[0])
        self.assertEqual(calls[2].args[1][:3],calls[3].args[1][:3])

    def test_query_rejects_unbounded_page(self):
        store=LivePostgresStore('etsy',connect=Mock())
        for kwargs in (dict(limit=201),dict(limit=0),dict(offset=-1)):
            with self.assertRaises(ValueError): store.query(**kwargs)
        store._connect.assert_not_called()

    def test_admit_is_not_a_pipeline_reset_or_rewrite(self):
        db=Mock()
        with patch('tools.s02_data.load.query',return_value=[dict(campaign_id='123456abcdef')]):
            result=admit_live(db,'test-live')
        self.assertEqual(result['status'],'LIVE')
        sql=db.sql.call_args_list[-1].args[0]
        self.assertIn('pg_advisory_xact_lock',sql)
        self.assertIn('INSERT INTO s02.live_batches',sql)
        self.assertIn("d.state='READY'",sql)
        self.assertNotIn('DELETE',sql)
        self.assertNotIn('checkpoint',sql)

    def test_missing_ready_admission_is_not_reported_success(self):
        with patch('tools.s02_data.load.query',return_value=[]):
            with self.assertRaisesRegex(ValueError,'READY'): admit_live(Mock(),'missing')

    def test_fixture_mode_cannot_silently_accept_generate(self):
        db=Mock(); db.command.return_value='s01'
        with self.assertRaisesRegex(ValueError,'live-up'): require_live(db)

    def test_worker_must_be_healthy_before_generate(self):
        db=Mock(); db.command.return_value='live-pg'
        for health in ('starting','unhealthy'):
            with patch('tools.s02_data.live.compose',return_value=json.dumps(dict(State='running',Health=health))):
                with self.assertRaisesRegex(ValueError,'healthy'): require_live(db)
        with patch('tools.s02_data.live.compose',return_value=json.dumps(dict(State='running',Health='healthy'))):
            require_live(db)

    def test_readiness_refuses_wrong_pipeline_mapping_or_clock(self):
        db=Mock(); db.command.side_effect=['live-pg','live-pg','misconfigured']
        with self.assertRaisesRegex(ValueError,'Airflow'): require_live(db)

    def test_missing_credentials_fail_before_pausing_or_sql(self):
        db=Mock()
        model=dict(services={s+'-sim':dict(environment={'S02_DB_PASSWORD':''}) for s in ('ebay','etsy')})
        with patch('tools.s02_data.live.compose',return_value=json.dumps(model)):
            with self.assertRaises(ValueError): up(db)
        db.command.assert_not_called(); db.sql.assert_not_called()

    def test_generate_publishes_after_prepare_and_repeat_needs_no_selector(self):
        calls=[]; names=[]
        def prepared(db,c):
            calls.append('prepare'); names.append(c['dataset']); return dict(dataset=c['dataset'])
        def admitted(db,name): calls.append('admit'); return dict(status='LIVE')
        with (
            patch.object(cli,'LocalDB'),
            patch('tools.s02_data.live.require_live_storage',side_effect=lambda db:calls.append('ready')),
            patch.object(cli,'prepare',side_effect=prepared),
            patch.object(cli,'admit_live',side_effect=admitted),
            patch.object(cli.uuid,'uuid4',side_effect=[Mock(hex='a'*32),Mock(hex='b'*32)]),
            patch.object(sys,'argv',['s02_data','generate','--config',str(ROOT/'tools/s02_data/config/quick_6min.json')]),
            patch('sys.stdout',new_callable=io.StringIO)
        ):
            cli.main(); cli.main()
        self.assertEqual(calls,['ready','prepare','admit']*2)
        self.assertEqual(len(set(names)),2)
        self.assertTrue(all(len(name)<=61 for name in names))

    def test_generation_storage_check_does_not_depend_on_airflow_or_source_uptime(self):
        db=Mock(); db.command.side_effect=RuntimeError('source stopped')
        with patch('tools.s02_data.live.query',return_value=[dict(relation_name='s02.live_batches')]),patch('sys.stdout',new_callable=io.StringIO):
            require_live_storage(db)
        self.assertEqual(db.command.call_count,2)
        self.assertTrue(all(c.args[0][2] in ('ebay-sim','etsy-sim') for c in db.command.call_args_list))

    def test_generation_refuses_known_fixture_source_mode(self):
        db=Mock(); db.command.return_value='s01'
        with patch('tools.s02_data.live.query',return_value=[dict(relation_name='s02.live_batches')]):
            with self.assertRaisesRegex(ValueError,'fixture/replay'): require_live_storage(db)

    def test_source_readiness_probes_authenticated_interfaces_not_health_only(self):
        model=dict(services={kind+'-sim':dict(ports=[dict(target=80,published=9001)],
            environment={kind.upper()+'_SIM_TOKEN':'synthetic-test-token'}) for kind in ('ebay','etsy')})
        with patch('tools.s02_data.live.urlopen',side_effect=[io.BytesIO(b'{"orders":[]}'),io.BytesIO(b'{"results":[]}')]) as http:
            probe_sources(model)
        self.assertEqual(http.call_count,2)
        self.assertTrue(all(c.args[0].get_header('Authorization')=='Bearer synthetic-test-token' for c in http.call_args_list))
        with patch('tools.s02_data.live.urlopen',side_effect=RuntimeError('private detail')):
            with self.assertRaisesRegex(RuntimeError,'live source read failed') as failure: probe_sources(model)
        self.assertNotIn('private detail',str(failure.exception))

    def test_observe_profile_reserves_all_lifecycle_branches_with_room(self):
        c=validate(json.loads((ROOT/'tools/s02_data/config/observe_6min.json').read_text()))
        batches=list(events(c))
        self.assertEqual(len(batches),18)
        self.assertEqual(sum(map(len,batches)),41)
        for batch in batches: validate_order(batch,c)

    def test_owner_window_refuses_pending_live_emissions_even_if_dags_idle(self):
        with patch.object(guard,'owner_sql',side_effect=['0','0','0','t','1']),patch.object(guard,'docker',return_value='owner-worker'):
            with self.assertRaisesRegex(guard.SafetyError,'producer quiet window'): guard.owner_idle('owner-pg')

    def test_live_marketplace_state_is_included_in_owner_signature(self):
        with patch.object(guard,'owner_sql',side_effect=['warehouse','website','t','live-a']):
            before=guard.protected_signature('owner-pg')
        with patch.object(guard,'owner_sql',side_effect=['warehouse','website','t','live-b']):
            after=guard.protected_signature('owner-pg')
        self.assertNotEqual(before,after)

    def test_startup_lock_refuses_concurrent_start_and_releases(self):
        with tempfile.TemporaryDirectory() as folder,patch('tools.s02_data.live.ROOT',Path(folder)):
            with startup_lock():
                with self.assertRaisesRegex(RuntimeError,'another live-up'):
                    with startup_lock(): pass
            with startup_lock(): pass

    def test_drain_leaves_retries_runnable_until_terminal(self):
        db=Mock()
        with patch('tools.s02_data.live.query',side_effect=[
                [dict(dag_id=d) for d in DAGS],
                [dict(dag_id='ebay_polling')],
                [dict(dag_id='ebay_polling')],[]]),patch('tools.s02_data.live.time.sleep'):
            drain(db)
        ebay=[c.args[0][-2] for c in db.command.call_args_list if c.args[0][-1]=='ebay_polling']
        self.assertEqual(ebay,['unpause','pause'])
        self.assertFalse(any('clear' in c.args[0] for c in db.command.call_args_list))

    def test_drain_refuses_unrelated_active_manual_run(self):
        db=Mock()
        with patch('tools.s02_data.live.query',side_effect=[[],[dict(dag_id='website_orders')]]):
            with self.assertRaisesRegex(ValueError,'manual/replay'): drain(db)
        db.command.assert_not_called()

    def test_composite_mapping_is_explicit_not_global_relaxation(self):
        macro=(ROOT/'transformations/macros/mapping_release_versions.sql').read_text()
        self.assertIn("var('mapping_version') == 'local-live-v1'",macro)
        self.assertIn("('s01-v1', 's02-catalog-v1')",macro)
        for path in ('candidates/candidate_order_line_snapshot_history.sql',
                     'ebay/ebay_candidate_order_line_snapshot_history.sql',
                     'etsy/etsy_candidate_order_line_snapshot_history.sql'):
            self.assertIn('mapping_release_versions()', (ROOT/'transformations/models'/path).read_text())

    def test_live_admission_schema_guards_identity_and_ready(self):
        sql=(ROOT/'migrations/marketplace_sim/003_live_batches.sql').read_text()
        for clause in ('live admission immutable','sealed READY','identity collision','REVOKE ALL'):
            self.assertIn(clause,sql)

    def test_db_backed_api_error_controls_apply_before_source_read(self):
        # Exercise actual HTTP handlers, not just a string assertion or fixture backend.
        for kind,module in [('ebay',ebay_api),('etsy',etsy_api)]:
            with self.subTest(kind=kind):
                store=LivePostgresStore(kind)
                store.query=Mock(return_value=([],0))
                with patch.object(module,'make_store',return_value=store):
                    state=module.State(ROOT/'fixtures/s01/source_states'/kind)
                if kind=='ebay': state.configure(dict(fail_offset=0,errors_left=1,error_status=429))
                else: state.configure(dict(errors_left=1,error_status=500))
                server=ThreadingHTTPServer(('127.0.0.1',0),module.handlers(state)[0])
                thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
                try:
                    path=('/sell/fulfillment/v1/order?filter=lastmodifieddate:[2026-11-01T00:00:00Z..2026-11-01T00:06:00Z]'
                        if kind=='ebay' else '/v3/application/shops/7001/receipts?min_last_modified=1&max_last_modified=2&limit=10&offset=0&sort_on=updated&sort_order=asc')
                    token=kind.upper()+'_SIM_TOKEN'
                    with patch.dict(os.environ,{token:'local-live-test'}):
                        request=Request(f'http://127.0.0.1:{server.server_port}'+path,headers={'Authorization':'Bearer local-live-test'})
                        with self.assertRaises(HTTPError) as error: urlopen(request,timeout=5)
                        self.assertEqual(error.exception.code,429 if kind=='ebay' else 500)
                        store.query.assert_not_called()
                        with urlopen(request,timeout=5) as response: self.assertEqual(response.status,200)
                        store.query.assert_called_once()
                finally:
                    server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__=='__main__': unittest.main(verbosity=2)
