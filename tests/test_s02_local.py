"""Offline local generator invariants; not scheduled/runtime acceptance."""
import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.s02_data.config import validate,parse_time,segments,sample_time,stream,zone
from tools.s02_data.generate import events
from tools.s02_data.load import validate_order,query
from tools.s02_data.playback import activate
from test_support.s02_oracle import facts
from tools.s02_data.references import references

ROOT=Path(__file__).resolve().parents[1]


def config(name='demo'):
    return validate(json.loads((ROOT/f'tools/s02_data/config/{name}.json').read_text()))


class LocalTests(unittest.TestCase):
    def test_custom_duration_with_blank_dates_is_resolved_once(self):
        raw=json.loads((ROOT/'tests/fixtures/s02_quick.json').read_text())
        for minutes in (5,6):
            raw['duration_minutes']=minutes
            with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
                clock.now.return_value=parse_time('2026-11-01T10:00:00Z')
                c=validate(raw)
            self.assertEqual(parse_time(c['end_at'])-parse_time(c['start_at']),timedelta(minutes=minutes))
            self.assertEqual(validate(c),c)
            batches=list(events(c))
            self.assertEqual(len(batches),18)
            for batch in batches:
                validate_order(batch,c)
                self.assertLess(parse_time(batch[-1]['visible_at']),parse_time(c['end_at']))
            for source,channel in c['channels'].items():
                selected=[b for b in batches if b[0]['source']==source]
                for branch,count in channel['required'].items():
                    reserved=[b for b in selected if b[0]['case']==branch]
                    self.assertGreaterEqual(len(reserved),count)
                    for b in reserved[:count]:
                        expected={'pending':1,'request':2,'cancel':3,'partial':2,
                                  'ship':2 if source=='etsy_sim' else 3}[branch]
                        self.assertEqual(len(b),expected)

    def test_custom_duration_with_explicit_start_and_explicit_end_precedence(self):
        raw=json.loads((ROOT/'tests/fixtures/s02_quick.json').read_text())
        raw['start_at']='2026-11-01T10:00:00+07:00'
        c=validate(raw)
        self.assertEqual(parse_time(c['end_at']),parse_time('2026-11-01T10:06:00+07:00'))
        raw['end_at']='2026-11-01T11:00:00+07:00'
        self.assertEqual(validate(raw)['end_at'],raw['end_at'])

    def test_invalid_duration_and_infeasible_short_lifecycle_refused(self):
        raw=json.loads((ROOT/'tests/fixtures/s02_quick.json').read_text())
        for minutes in (0,-1,True,5.5,'6',None,527041):
            with self.subTest(minutes=minutes):
                bad=copy.deepcopy(raw); bad['duration_minutes']=minutes
                with self.assertRaises(ValueError): validate(bad)
        raw['channels']['internal_web']['delay_seconds']=[60,3600]
        with self.assertRaisesRegex(ValueError,'range too short for required lifecycle'):
            validate(raw)

    def test_missing_dates_resolve_once_and_normalized_config_stays_fixed(self):
        raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
        raw.pop('start_at'); raw.pop('end_at')
        now=datetime(2026,10,31,3,15,30,123456,tzinfo=timezone.utc)
        with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
            clock.now.return_value=now
            c=validate(raw)
            clock.now.assert_called_once_with(timezone.utc)
        self.assertEqual(parse_time(c['start_at']),now.replace(microsecond=0))
        self.assertEqual(parse_time(c['end_at']),now.replace(microsecond=0)+timedelta(hours=5))
        self.assertNotIn('start_at',raw)
        with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
            self.assertEqual(validate(c),c)
            clock.now.assert_not_called()
        for channel in c['channels'].values():
            self.assertEqual(channel['start_at'],c['start_at'])
            self.assertEqual(channel['end_at'],c['end_at'])

    def test_explicit_start_missing_end_defaults_to_five_elapsed_hours(self):
        raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
        raw.pop('end_at')
        c=validate(raw)
        self.assertEqual(c['start_at'],raw['start_at'])
        self.assertEqual(parse_time(c['end_at'])-parse_time(c['start_at']),timedelta(hours=5))
        self.assertEqual(list(events(c)),list(events(validate(c))))

    def test_missing_start_preserves_explicit_end(self):
        raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
        raw.pop('start_at')
        with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
            clock.now.return_value=parse_time('2026-10-30T10:00:00Z')
            c=validate(raw)
        self.assertEqual(c['end_at'],raw['end_at'])

    def test_null_and_empty_global_dates_use_defaults(self):
        for missing in (None,''):
            raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
            raw.update(start_at=missing,end_at=missing)
            with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
                clock.now.return_value=parse_time('2026-10-31T10:00:00Z')
                c=validate(raw)
            self.assertEqual(parse_time(c['start_at']),parse_time('2026-10-31T10:00:00Z'))
            self.assertEqual(parse_time(c['end_at']),parse_time('2026-10-31T15:00:00Z'))

    def test_explicit_channel_range_keeps_override_with_default_global_range(self):
        raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
        raw.pop('start_at'); raw.pop('end_at')
        raw['channels']['ebay_sim'].update(start_at='2026-10-20T00:00:00Z',end_at='2026-10-21T00:00:00Z')
        c=validate(raw)
        self.assertEqual(c['channels']['ebay_sim']['start_at'],'2026-10-20T00:00:00Z')
        self.assertEqual(c['channels']['ebay_sim']['end_at'],'2026-10-21T00:00:00Z')

    def test_explicit_end_before_default_now_is_refused(self):
        raw=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text())
        raw.pop('start_at')
        with patch('tools.s02_data.config.datetime',wraps=datetime) as clock:
            clock.now.return_value=parse_time('2026-11-01T00:00:00Z')
            with self.assertRaisesRegex(ValueError,'range must be'):
                validate(raw)

    def test_sql_json_array_may_span_multiple_lines(self):
        db=Mock(); db.sql.return_value='[{"order_id":"A"},\n {"order_id":"B"}]\n'
        self.assertEqual(query(db,'SELECT 1'),[dict(order_id='A'),dict(order_id='B')])

    def test_counts_and_source_money_mapping_purchase_validation(self):
        c=config(); batches=list(events(c)); counts={s:0 for s in c['channels']}
        for batch in batches:
            validate_order(batch,c)
            counts[batch[0]['source']]+=1
            for e in batch:
                facts(e,references()['mapping'])
                channel=c['channels'][e['source']]
                self.assertLess(parse_time(e['visible_at']),parse_time(channel['end_at']))
                self.assertGreaterEqual(parse_time(e['visible_at']),parse_time(channel['start_at']))
        self.assertEqual(counts,{s:v['orders'] for s,v in c['channels'].items()})

    def test_repeatability_and_independent_channels(self):
        c=config(); before=list(events(c)); self.assertEqual(before,list(events(c)))
        c['channels']['ebay_sim']['orders']+=2
        after=list(events(c))
        self.assertEqual([b for b in before if b[0]['source']=='internal_web'],
                         [b for b in after if b[0]['source']=='internal_web'])

    def test_event_seed_keeps_initial_purchases(self):
        c=config(); a=list(events(c)); c['event_seed']+=1; b=list(events(c))
        self.assertEqual([(x[0]['visible_at'],x[0]['payload']) for x in a],
                         [(x[0]['visible_at'],x[0]['payload']) for x in b])
        self.assertNotEqual(a,b)

    def test_required_cases_are_complete(self):
        c=config('coverage'); found={s:{} for s in c['channels']}
        for batch in events(c):
            e=batch[0]; found[e['source']][e['case']]=found[e['source']].get(e['case'],0)+1
            if e['case']=='cancel': self.assertEqual(batch[-1]['payload']['orders'][0]['cancellation_status'],'CANCELED')
            if e['source']=='ebay_sim' and e['case']=='ship': self.assertEqual(batch[-1]['payload']['order']['orderFulfillmentStatus'],'FULFILLED')
        for s,v in c['channels'].items():
            for branch,n in v['required'].items(): self.assertGreaterEqual(found[s].get(branch,0),n)

    def test_peak_weight_distribution_and_overnight(self):
        start=parse_time('2026-10-20T00:00:00Z'); end=start+timedelta(days=1)
        parts=segments(start,end,zone('UTC'),[dict(start='00:00',end='12:00',weight=3)])
        rng=stream(17,'test',0,'time')
        peak=sum(sample_time(parts,rng).hour<12 for _ in range(10000))
        self.assertTrue(7200<peak<7800,peak)
        self.assertTrue(segments(start,end,zone('UTC'),[dict(start='22:00',end='02:00',weight=2)]))

    def test_bad_config_is_refused(self):
        for modify in (
            lambda c:c['channels']['ebay_sim'].update(required={'partial':1}),
            lambda c:c['channels']['etsy_sim'].update(notifications={'omit':1,'duplicate':0}),
            lambda c:c.update(start_at='2026-10-20T00:00:00'),
            lambda c:c['channels']['internal_web'].update(required={'cancel':999}),
            lambda c:c['channels']['internal_web'].update(unknown=True),
        ):
            c=json.loads((ROOT/'tools/s02_data/config/demo.json').read_text()); modify(c)
            with self.assertRaises((ValueError,KeyError)): validate(c)

    def test_faults_are_opt_in_and_source_specific(self):
        c=config('faults'); batches=list(events(c))
        etsy=[b for b in batches if b[0]['source']=='etsy_sim']
        self.assertEqual(sum(not b[0]['notify'] for b in etsy),1)
        self.assertEqual(sum(b[0]['duplicate'] for b in etsy),1)
        c['channels']['etsy_sim']['notifications']={'duplicate':1}
        self.assertEqual(validate(c)['channels']['etsy_sim']['notifications'],{'omit':0,'duplicate':1})

    def test_activation_requires_confirmation_before_db(self):
        db=Mock()
        with self.assertRaises(ValueError): activate(db,'test','replay',None,False)
        db.sql.assert_not_called()

    def test_dirty_local_scope_refused_without_any_write(self):
        db=Mock()
        db.sql.side_effect=[json.dumps([dict(campaign_id='abcdef123456',state='READY',config={})]),
                            '[]','[{"n":1}]','[{"n":1}]','[{"n":0}]','[]']
        with self.assertRaisesRegex(ValueError,'local data/checkpoints'):
            activate(db,'local-demo','replay','2026-10-20T00:00:00Z',True)
        self.assertTrue(all(call.args[0].startswith('SELECT') for call in db.sql.call_args_list))


if __name__=='__main__': unittest.main(verbosity=2)
