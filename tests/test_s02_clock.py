"""Offline HTTP clock isolation checks; pipeline never reads simulator backing DB."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from orchestration import source_clock


class ClockTests(unittest.TestCase):
    def response(self,**overrides):
        value=dict(campaign_id='abcdef123456',mode='replay',now='2026-10-20T01:00:00+07:00',
                   initial_start='2026-10-20T01:00:00+07:00',running=True)
        value.update(overrides)
        response=MagicMock(); response.__enter__.return_value=response
        response.status=200; response.read.return_value=json.dumps(value).encode()
        return response

    def test_default_s01_never_calls_clock(self):
        with patch.dict(os.environ,{},clear=True),patch.object(source_clock,'urlopen') as request:
            self.assertIsNone(source_clock.read()); request.assert_not_called()

    def test_local_clock_http_and_dataset_scope(self):
        env=dict(S02_LOCAL_PLAYBACK='true',S02_CAMPAIGN_ID='abcdef123456',EBAY_ORIGIN='http://ebay-sim',EBAY_SIM_TOKEN='test')
        with patch.dict(os.environ,env,clear=True),patch.object(source_clock,'urlopen',return_value=self.response()) as request:
            value=source_clock.read(); self.assertEqual(value['mode'],'replay')
            self.assertEqual(request.call_args.args[0].full_url,'http://ebay-sim/s02/clock')
        with patch.dict(os.environ,env,clear=True),patch.object(source_clock,'urlopen',return_value=self.response(campaign_id='other')):
            with self.assertRaises(ValueError): source_clock.read()

    def test_naive_time_refused(self):
        env=dict(S02_LOCAL_PLAYBACK='true',S02_CAMPAIGN_ID='abcdef123456',EBAY_ORIGIN='http://ebay-sim',EBAY_SIM_TOKEN='test')
        with patch.dict(os.environ,env,clear=True),patch.object(source_clock,'urlopen',return_value=self.response(now='2026-10-20T01:00:00')):
            with self.assertRaises(ValueError): source_clock.read()


if __name__=='__main__': unittest.main(verbosity=2)
