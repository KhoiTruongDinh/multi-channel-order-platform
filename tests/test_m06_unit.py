"""Offline security and source-boundary regression, no DB writes or HTTP calls."""
import base64
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.etsy_common import signature, verify, validate_url, now, receipt_url
from ingestion.etsy import retry_after_seconds


class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.at = now()
        self.raw = b'{"shop_id":7001,"event_type":"order.paid"}'
        self.key = b'public-synthetic-key'
        self.stamp = str(int(self.at.timestamp()))
        self.headers = {'webhook-id':'unit-1','webhook-timestamp':self.stamp,
                        'webhook-signature':signature('unit-1',self.stamp,self.raw,self.key)}

    def test_valid_and_multiple_signatures(self):
        self.assertEqual(verify(self.headers,self.raw,self.at,self.key),(True,True))
        self.headers['webhook-signature']='v1,invalid '+self.headers['webhook-signature']
        self.assertEqual(verify(self.headers,self.raw,self.at,self.key),(True,True))

    def test_raw_byte_mutation(self):
        self.assertFalse(verify(self.headers,self.raw+b' ',self.at,self.key)[0])

    def test_missing_and_malformed_headers(self):
        self.assertEqual(verify({},self.raw,self.at,self.key),(False,False))
        self.headers['webhook-timestamp']='not-an-epoch'
        self.assertEqual(verify(self.headers,self.raw,self.at,self.key),(False,False))

    def test_old_and_future_clocks(self):
        for delta in (-301,301):
            self.assertEqual(verify(self.headers,self.raw,self.at+timedelta(seconds=delta),self.key),(True,False))

    def test_foreign_url_and_shop(self):
        os.environ['ETSY_ORIGIN']='http://etsy-sim'
        self.assertEqual(validate_url('http://etsy-sim/v3/application/shops/7001/receipts/9001001',7001),'9001001')
        self.assertEqual(validate_url('http://etsy-sim/v3/application/shops/7001/receipts/9001001','07001'),'9001001')
        for url in ('http://evil/v3/application/shops/7001/receipts/9001001',
                    'http://etsy-sim/v3/application/shops/7002/receipts/9001001',
                    'http://etsy-sim/v3/application/shops/7001/receipts/9001001?token=x',
                    'http://user@etsy-sim/v3/application/shops/7001/receipts/9001001'):
            with self.assertRaises(ValueError):
                validate_url(url,7001)

    def test_database_failure_never_acknowledged(self):
        from ingestion.etsy_receiver import Receiver
        server=ThreadingHTTPServer(('127.0.0.1',0),Receiver)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        os.environ['ETSY_SIGNING_SECRET']='whsec_'+base64.b64encode(self.key).decode()
        thread.start()
        try:
            with patch('ingestion.etsy_receiver.connect',side_effect=RuntimeError('DB unavailable')):
                body=json.dumps({'shop_id':7001,'event_type':'order.paid','resource_url':receipt_url(9001001)}).encode()
                headers=dict(self.headers,**{'webhook-signature':signature('unit-1',self.stamp,body,self.key)})
                with self.assertRaises(HTTPError) as response:
                    urlopen(Request(f'http://127.0.0.1:{server.server_port}/webhooks/etsy',data=body,headers=headers),timeout=5)
                self.assertEqual(response.exception.code,503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_retry_after_is_not_silently_capped(self):
        self.assertEqual(retry_after_seconds({'Retry-After':'3600'},self.at),3600)
        self.assertEqual(retry_after_seconds({'retry-after':'Wed, 28 Oct 2026 10:00:00 GMT'},
            self.at.replace(year=2026,month=10,day=28,hour=9,minute=0,second=0,microsecond=0)),3600)
        self.assertEqual(retry_after_seconds({'Retry-After':'invalid'},self.at),0)
        with self.assertRaises(ValueError):
            retry_after_seconds({'Retry-After':'Infinity'},self.at)


if __name__=='__main__':
    unittest.main(verbosity=2)
