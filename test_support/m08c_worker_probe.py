"""Independent processes, real leases and receiver commit-before-ACK loss."""
import json
import multiprocessing
import os
import time
from http.client import RemoteDisconnected
from http.server import ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid

from ingestion.etsy_common import connect, enqueue, signature, secret, receipt_url
from ingestion.etsy import claim, process


def stale_worker(pipe, work):
    with connect() as conn:
        lease = claim(conn, [work])
        pipe.send(lease)
        pipe.recv()
        try:
            process(conn, lease)
        except RuntimeError as error:
            pipe.send(str(error))
        else:
            pipe.send('UNEXPECTED_SUCCESS')


def lease_fencing():
    context = multiprocessing.get_context('spawn')
    with connect() as conn:
        work = enqueue(conn, 'm08c-concurrent-' + uuid.uuid4().hex, 9001001, None)
    parent, child = context.Pipe()
    worker = context.Process(target=stale_worker, args=(child, work))
    worker.start()
    try:
        assert parent.poll(30), 'old worker did not claim lease'
        old = parent.recv()
        with connect() as conn:
            conn.execute("UPDATE ops.processing_work SET lease_until=clock_timestamp()-INTERVAL '1 second' WHERE work_id=%s", (work,))
        with connect() as conn:
            new = claim(conn, [work])
            assert new[-1] != old[-1] and new[3] == old[3] + 1
            assert process(conn, new)
        parent.send('return')
        assert parent.poll(30) and 'lease lost' in parent.recv()
        worker.join(10)
        assert worker.exitcode == 0
        with connect() as conn:
            assert conn.execute('SELECT state,cycle_attempts FROM ops.processing_work WHERE work_id=%s', (work,)).fetchone() == ('SUCCEEDED', 2)
            assert conn.execute("SELECT count(*) FROM raw.raw_records WHERE run_id=%s AND resource_type='etsy_receipt'", (new[1],)).fetchone()[0] == 1
    finally:
        if worker.is_alive():
            worker.terminate()
            worker.join(10)
        parent.close()
        child.close()
    return dict(work_id=str(work), stale_completion_rejected=True, successful_raw=1)


def receiver(pipe, crash):
    from ingestion.etsy_receiver import Receiver

    class Handler(Receiver):
        def send_response(self, code, message=None):
            if crash and code == 202:
                os._exit(97)
            return super().send_response(code, message)

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        pipe.send(server.server_port)
        server.serve_forever()


def lost_ack():
    context = multiprocessing.get_context('spawn')
    identity = 'm08c-ack-' + uuid.uuid4().hex
    body = json.dumps(dict(shop_id=7001, event_type='order.paid', resource_url=receipt_url(9001001))).encode()
    for crash in (True, False):
        parent, child = context.Pipe()
        worker = context.Process(target=receiver, args=(child, crash))
        worker.start()
        try:
            assert parent.poll(30), 'receiver did not bind test port'
            port = parent.recv()
            stamp = str(int(time.time()))
            headers = {'webhook-id': identity, 'webhook-timestamp': stamp,
                       'webhook-signature': signature(identity, stamp, body, secret())}
            try:
                with urlopen(Request(f'http://127.0.0.1:{port}/webhooks/etsy', data=body, headers=headers), timeout=20) as response:
                    assert not crash and response.status == 202
            except (RemoteDisconnected, URLError, ConnectionResetError):
                assert crash
            if crash:
                worker.join(10)
                assert worker.exitcode == 97
            with connect() as conn:
                inbox = conn.execute('SELECT inbox_id FROM ops.webhook_inbox WHERE webhook_id=%s', (identity,)).fetchall()
                assert len(inbox) == 1, 'ACK loss lost or duplicated inbox'
                assert conn.execute('SELECT count(*) FROM ops.processing_work WHERE inbox_id=%s', (inbox[0][0],)).fetchone()[0] == 1
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(10)
            parent.close()
            child.close()
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM ops.webhook_delivery_attempts WHERE webhook_id=%s', (identity,)).fetchone()[0] == 2
    return dict(webhook_id=identity, durable_inbox=1, delivery_audits=2)


if __name__ == '__main__':
    import sys
    result = lease_fencing() if sys.argv[1] == 'abrupt_lease_owner' else lost_ack()
    print(json.dumps(dict(status='PASS', **result)))
