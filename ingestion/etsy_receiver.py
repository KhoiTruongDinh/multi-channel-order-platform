"""Local always-on webhook receiver: bounded read, raw-byte verification, durable ACK."""
import json
import os
import socket
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ingestion.etsy_common import (connect, now, secret, shop, uid, verify, validate_url,
                                   start_run, finish_run, raw_record, enqueue, decode_json)


def receive(body, headers):
    received = now()
    valid, fresh = verify(headers, body, received, secret(), int(os.environ.get('ETSY_FRESHNESS_SECONDS', '300')))
    status, reason, payload, inbox = 202, None, None, None
    try:
        if not valid or not fresh:
            status = 401
            raise ValueError('invalid signature or delivery freshness')
        payload = decode_json(body)
        receipt = validate_url(payload['resource_url'], payload['shop_id'])
        if not isinstance(payload['event_type'], str) or not payload['event_type']:
            raise ValueError('missing event type')
    except (ValueError, KeyError, TypeError, UnicodeError):
        status = 401 if status == 401 else 400
        reason = 'SIGNATURE_OR_FRESHNESS' if status == 401 else 'INVALID_NOTIFICATION'
    subscription = os.environ.get('ETSY_SUBSCRIPTION_ID', 'local-s01')
    run, delivery = uuid.uuid4(), uuid.uuid4()
    with connect() as conn:
        start_run(conn, run, 'webhook', f'm06:delivery:{delivery}')
        prior = None
        if reason is None:
            key = f'inbox:{subscription}:{headers["webhook-id"]}'
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (key,))
            prior = conn.execute('''SELECT i.inbox_id,r.raw_bytes FROM ops.webhook_inbox i
                JOIN raw.raw_records r ON r.raw_record_id=i.first_raw_record_id
                WHERE i.source_system='etsy_sim' AND i.subscription_id=%s AND i.webhook_id=%s''',
                (subscription, headers['webhook-id'])).fetchone()
            if prior and bytes(prior[1]) != body:
                status, reason = 409, 'CONFLICTING_MESSAGE_BODY'
        raw_id, _ = raw_record(conn, run, 'etsy_webhook', '/webhooks/etsy', 'POST', status, body, headers)
        if reason is None:
            inbox = prior[0] if prior else uid(key)
            supported = payload['event_type'] in ('order.paid', 'order.shipped')
            if not prior:
                conn.execute('''INSERT INTO ops.webhook_inbox
                    (inbox_id,source_system,subscription_id,webhook_id,event_type,source_account_id,
                     resource_url,first_raw_record_id,first_received_at,fetch_state)
                    VALUES (%s,'etsy_sim',%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (inbox, subscription, headers['webhook-id'], payload['event_type'], shop(),
                     payload['resource_url'], raw_id, received, 'PENDING' if supported else 'IGNORED'))
                if supported:
                    enqueue(conn, key, receipt, raw_id, inbox)
        conn.execute('''INSERT INTO ops.webhook_delivery_attempts
            (delivery_id,source_system,subscription_id,webhook_id,inbox_id,raw_record_id,
             received_at,signature_valid,freshness_valid,accepted,response_status,rejection_reason)
            VALUES (%s,'etsy_sim',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (delivery, subscription, headers.get('webhook-id'), inbox, raw_id, received,
             valid, fresh, reason is None, status, reason))
        finish_run(conn, run, reason is None, reason)
    return status, {'delivery_id': str(delivery), 'accepted': reason is None, 'reason': reason}


class Receiver(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def respond(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reject_transport(self, status, reason):
        # No unbounded body read: retain a labeled transport-rejection audit only.
        run, delivery = uuid.uuid4(), uuid.uuid4()
        subscription = os.environ.get('ETSY_SUBSCRIPTION_ID','local-s01')
        try:
            with connect() as conn:
                start_run(conn,run,'webhook',f'm06:transport:{delivery}')
                raw, _ = raw_record(conn,run,'etsy_transport_rejection',self.path,'POST',status,b'',{},
                                    metadata={'body_not_read':True,'reason':reason})
                conn.execute('''INSERT INTO ops.webhook_delivery_attempts
                    (delivery_id,source_system,subscription_id,raw_record_id,received_at,
                     signature_valid,freshness_valid,accepted,response_status,rejection_reason)
                    VALUES (%s,'etsy_sim',%s,%s,%s,false,false,false,%s,%s)''',
                    (delivery,subscription,raw,now(),status,reason))
                finish_run(conn,run,False,reason)
        except Exception:
            status=503
        self.close_connection=True
        self.respond(status,{'error':reason})

    def do_GET(self):
        if self.path != '/health':
            return self.respond(404, {})
        try:
            with connect() as conn:
                conn.execute('SELECT 1')
            self.respond(200, {'status': 'ok'})
        except Exception:
            self.respond(503, {'status': 'database unavailable'})

    def do_POST(self):
        if self.path != '/webhooks/etsy':
            return self.respond(404, {})
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            return self.reject_transport(400, 'one Content-Length required')
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length <= 65536:
                return self.reject_transport(413, 'body size limit')
            names = ('webhook-id', 'webhook-timestamp', 'webhook-signature')
            if any(len(self.headers.get_all(name, [])) > 1 for name in names):
                return self.reject_transport(400, 'ambiguous signing headers')
            headers = {name: self.headers.get(name, '') for name in names}
            if any(len(value) > 2000 for value in headers.values()):
                return self.reject_transport(431, 'header size limit')
            body = self.rfile.read(length)
            if len(body) != length:
                return self.reject_transport(400, 'incomplete body')
            status, result = receive(body, headers)
        except (ValueError, socket.timeout):
            return self.reject_transport(400, 'invalid or timed-out request')
        except Exception:
            status, result = 503, {'error': 'persistence unavailable; retry delivery'}
        self.respond(status, result)


if __name__ == '__main__':
    secret()  # Fail startup on invalid configuration without printing credentials.
    shop()
    if not 0 <= int(os.environ.get('ETSY_FRESHNESS_SECONDS','300')) <= 3600:
        raise ValueError('freshness must be between 0 and 3600 seconds')
    ThreadingHTTPServer(('0.0.0.0', 8000), Receiver).serve_forever()
