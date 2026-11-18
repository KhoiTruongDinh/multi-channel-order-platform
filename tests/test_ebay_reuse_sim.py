"""Small loopback SIM contract tests; no Docker stack or warehouse campaign."""
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from simulator.ebay_api import State,handlers,ROOT
from simulator.http_faults import Faults


class SimTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,EBAY_SIM_TOKEN='unit-token'); self.env.start(); self.addCleanup(self.env.stop)
        with patch('simulator.ebay_api.make_store',return_value=None):
            self.state=State(Path(__file__).resolve().parents[1]/'fixtures/s01/source_states/ebay')
        api,_=handlers(self.state)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),api)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def get(self,path):
        req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,headers={'Authorization':'Bearer unit-token'})
        with urlopen(req,timeout=5) as response: return json.load(response)

    def test_ids_take_precedence_and_preserve_list_cancellation_gap(self):
        identity=self.state.data['order']['orderId']
        self.state.data['order']['cancelStatus']['cancelRequests']=[{'cancelRequestId':'c1'}]
        result=self.get(ROOT+'?'+urlencode(dict(orderIds=identity,filter='invalid',offset='invalid',limit='invalid')))
        self.assertEqual([o['orderId'] for o in result['orders']],[identity])
        self.assertEqual(result['orders'][0]['cancelStatus']['cancelRequests'],[])
        self.assertEqual(self.get(ROOT+'/'+identity)['cancelStatus']['cancelRequests'],[{'cancelRequestId':'c1'}])

    def test_50_limit_empty_duplicate_and_missing_membership(self):
        ids=[f'order-{i}' for i in range(50)]
        self.assertEqual(self.get(ROOT+'?'+urlencode({'orderIds':','.join(ids)}))['orders'],[])
        for values in (ids+['order-51'],['same','same'],['']):
            with self.assertRaises(HTTPError) as error:
                self.get(ROOT+'?'+urlencode({'orderIds':','.join(values)}))
            self.assertEqual(error.exception.code,400)

    def test_two_fault_delays_overlap_without_double_consuming_counter(self):
        self.state.faults=Faults(dict(kind='timeout',count=2,delay_seconds=.01))
        barrier=threading.Barrier(2); original=Faults.response
        def response(local,path,status):
            if local.left: barrier.wait(timeout=3)
            return original(local,path,status)
        identity=self.state.data['order']['orderId']
        with patch.object(Faults,'response',response),ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.get,ROOT+'/'+identity) for _ in range(2)]
            self.assertEqual([f.result()['orderId'] for f in futures],[identity,identity])
        self.assertEqual(self.state.faults.left,0)


if __name__=='__main__': unittest.main()
