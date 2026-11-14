"""Private HTTP sources/receiver for the real all-source scheduler gate.

Only test setup reads source fixtures. Production collectors use SQL/HTTP.
No host listeners or owner credentials are used.
"""
import base64
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
KEY=b'disposable-scheduler-signing-key'
SECRET='whsec_'+base64.b64encode(KEY).decode()


def serve():
    assert os.environ['PLATFORM_DB_HOST'].startswith('delta-sched-pg-'), 'private test PostgreSQL required'
    from simulator import ebay_api, etsy_api
    from simulator.s02_store import Store
    from ingestion.etsy_receiver import Receiver
    os.environ['SIMULATOR_MODE']='s01'
    ebay=ebay_api.State(ROOT/'fixtures/s01/source_states/ebay')
    etsy=etsy_api.State(ROOT/'fixtures/s01/source_states/etsy')
    ebay.s02=Store('ebay')
    etsy.s02=Store('etsy')

    class Control(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def do_POST(self):
            if self.path!='/advance':
                self.send_error(404)
                return
            stamp=datetime.now(timezone.utc)
            doc=json.loads((ROOT/'fixtures/s01/source_states/ebay/0902.json').read_text())
            doc['order']['lastModifiedDate']=stamp.isoformat()
            with ebay.lock:
                ebay.s02.upsert(doc)
            with etsy.lock:
                for offset in (0,1):
                    receipt=copy.deepcopy(etsy.receipt)
                    receipt['receipt_id']+=offset
                    receipt['updated_timestamp']=int(stamp.timestamp())
                    for line in receipt['transactions']:
                        line['receipt_id']=receipt['receipt_id']
                        line['transaction_id']+=offset*100
                    for shipment in receipt['shipments']:
                        shipment['receipt_shipping_id']+=offset*100
                    etsy.s02.upsert(receipt)
            # The second receipt has NO notification: recovery must discover it.
            from ingestion.etsy_common import signature
            body=json.dumps(dict(event_type='order.paid',shop_id=7001,
                resource_url=os.environ['ETSY_ORIGIN']+'/v3/application/shops/7001/receipts/'+str(etsy.receipt['receipt_id']))).encode()
            timestamp=str(int(stamp.timestamp()))
            headers={'webhook-id':'delta-scheduled-paid','webhook-timestamp':timestamp,
                     'webhook-signature':signature('delta-scheduled-paid',timestamp,body,KEY),
                     'Content-Type':'application/json'}
            with urlopen(Request('http://127.0.0.1:18083/webhooks/etsy',data=body,headers=headers),timeout=10) as response:
                assert response.status==202
            self.send_response(204)
            self.end_headers()

    for port,handler in ((18081,ebay_api.handlers(ebay)[0]),
                         (18082,etsy_api.handlers(etsy)[0]),(18083,Receiver)):
        server=ThreadingHTTPServer(('0.0.0.0',port),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',18084),Control).serve_forever()


if __name__=='__main__':
    serve()
