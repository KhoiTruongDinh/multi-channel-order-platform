"""Actual receiver/API/leased acquisition: old notification never invents old snapshots."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
import uuid

from ingestion.etsy_common import connect, signature, secret, receipt_url


def cli(*args):
    env = {key: value for key, value in os.environ.items() if key not in
           ('ETSY_SIGNING_SECRET','MARKETPLACE_WRITER_PASSWORD','WEBSITE_WRITER_PASSWORD')}
    result = subprocess.run([sys.executable, '-m', 'ingestion.etsy', *args], capture_output=True, text=True, timeout=180, env=env)
    assert result.returncode == 0, 'Etsy recovery failed; retain case audit'


def main():
    identity = 'm08c-ordering-' + uuid.uuid4().hex
    try:
        with urlopen(Request('http://etsy-sim:8081/control', data=b'{"state":"0905","extra_receipt":true}'), timeout=10) as response:
            assert response.status == 200
        # Source already shipped; deliver shipped then a late paid notification.
        for index, event in enumerate(('order.shipped', 'order.paid', 'order.paid')):
            message = identity + ('-shipped' if index == 0 else '-paid')
            body = json.dumps(dict(shop_id=7001, event_type=event, resource_url=receipt_url(9001001))).encode()
            stamp = str(int(time.time()))
            headers = {'webhook-id': message, 'webhook-timestamp': stamp,
                       'webhook-signature': signature(message, stamp, body, secret())}
            with urlopen(Request('http://etsy-receiver:8000/webhooks/etsy', data=body, headers=headers), timeout=15) as response:
                assert response.status == 202
            cli('drain', '--execution-id', identity + '-drain-' + str(index))
        # No notification at all for 9001002: independently recover via receipt API.
        stream = 'receipts_test_' + uuid.uuid4().hex
        cli('recovery', '--execution-id', identity + '-omitted', '--checkpoint-stream', stream,
            '--window-start', '2026-10-17T09:04:00Z', '--window-end', '2026-10-17T09:06:00Z')
        with connect() as conn:
            inbox = conn.execute('SELECT count(*) FROM ops.webhook_inbox WHERE webhook_id LIKE %s', (identity + '%',)).fetchone()[0]
            attempts = conn.execute('SELECT count(*) FROM ops.webhook_delivery_attempts WHERE webhook_id LIKE %s', (identity + '%',)).fetchone()[0]
            assert inbox == 2 and attempts == 3
            omitted = conn.execute("SELECT count(*) FROM raw.raw_records WHERE resource_type='etsy_receipt' AND parsed_payload->>'receipt_id'='9001002'").fetchone()[0]
            assert omitted > 0
            assert conn.execute("SELECT count(*) FROM ops.webhook_inbox WHERE resource_url LIKE '%/9001002'").fetchone()[0] == 0
            observed = conn.execute("""SELECT r.parsed_payload->>'is_shipped' FROM raw.raw_records r
                JOIN ops.etsy_work_context c USING(run_id) JOIN ops.processing_work w USING(work_id)
                JOIN ops.webhook_inbox i USING(inbox_id)
                WHERE r.resource_type='etsy_receipt' AND i.webhook_id LIKE %s""", (identity + '%',)).fetchall()
            # Both notifications fetch current source; no invented paid-only snapshot.
            assert observed and all(row == ('true',) for row in observed)
    finally:
        with urlopen(Request('http://etsy-sim:8081/control', data=b'{"state":"0905"}'), timeout=10) as response:
            assert response.status == 200
    print(json.dumps(dict(status='PASS', message_prefix=identity, inbox=2, deliveries=3,
                         omitted_receipt='9001002', recovery_stream=stream)))


if __name__ == '__main__':
    main()
