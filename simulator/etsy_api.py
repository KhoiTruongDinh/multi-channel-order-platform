"""Fixed Etsy HTTP subset; controls are test-only and on a separate listener."""
import json
import copy
import os
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from simulator.s02_store import Store, control as handle_control
from simulator.s02_temporal import make_store, PostgresStore
from simulator.http_faults import Faults


class State:
    def __init__(self, fixtures='/fixtures/etsy'):
        self.fixtures = Path(fixtures)
        self.lock = threading.Lock()
        self.s02 = make_store('etsy')
        self.configure({})

    def configure(self, config):
        faults = Faults(config.get('transport_fault'))
        name = config.get('state', '0905')
        if name not in ('0904', '0905'):
            raise ValueError('unsupported state')
        with self.lock:
            self.receipt = (json.loads((self.fixtures / f'{name}.json').read_text())
                            if self.s02 is None else {})
            self.status = int(config.get('error_status', 500))
            self.errors = int(config.get('errors_left', 0))
            self.faults = faults
            self.extra_receipt = bool(config.get('extra_receipt', False))


def extra_receipt(base):
    """One explicit test-only omitted-notification receipt; fixed mode unchanged."""
    value = copy.deepcopy(base)
    value['receipt_id'] = 9001002
    for transaction in value['transactions']:
        transaction['receipt_id'] = 9001002
        transaction['transaction_id'] += 100
    for shipment in value['shipments']:
        shipment['receipt_shipping_id'] += 100
    return value


def handlers(state):
    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value):
            broken = state.faults.response(self.path, status)
            body = broken if broken is not None else json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            if status == 429:
                self.send_header('Retry-After', '1')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path == '/health':
                return self.reply(200, {'status': 'ok'})
            if self.headers.get('Authorization') != 'Bearer ' + os.environ['ETSY_SIM_TOKEN']:
                return self.reply(401, {})
            parsed = urlsplit(self.path)
            match = re.fullmatch(r'/v3/application/shops/7001/receipts(?:/([1-9][0-9]*))?', parsed.path)
            if not match:
                return self.reply(404, {})
            try:
                with state.lock:
                    if state.errors:
                        state.errors -= 1
                        return self.reply(state.status, {'error': 'intentional test fault'})
                    if match[1]:
                        if state.s02 is not None:
                            row = state.s02.get(match[1]) if isinstance(state.s02,PostgresStore) else state.s02.rows.get(match[1])
                            return self.reply(200, row) if row else self.reply(404, {})
                        if match[1] == str(state.receipt['receipt_id']):
                            return self.reply(200, state.receipt)
                        if state.extra_receipt and match[1] == '9001002':
                            return self.reply(200, extra_receipt(state.receipt))
                        return self.reply(404, {})
                    q = parse_qs(parsed.query, strict_parsing=True)
                    if any(len(v) != 1 for v in q.values()) or set(q) != {'min_last_modified','max_last_modified','limit','offset','sort_on','sort_order'}:
                        raise ValueError('explicit query required')
                    start, end, limit, offset = (int(q[k][0]) for k in ('min_last_modified','max_last_modified','limit','offset'))
                    if start > end or not 1 <= limit <= 100 or offset < 0 or q['sort_on'] != ['updated'] or q['sort_order'] != ['asc']:
                        raise ValueError('invalid bounds or sort')
                    if isinstance(state.s02,PostgresStore):
                        from datetime import datetime,timezone
                        rows,total=state.s02.query(start=datetime.fromtimestamp(start,timezone.utc),
                            end=datetime.fromtimestamp(end,timezone.utc),limit=limit,offset=offset)
                        return self.reply(200, {'count':total,'results':rows})
                    available = state.s02.rows.values() if state.s02 is not None else (
                        [state.receipt, extra_receipt(state.receipt)] if state.extra_receipt else [state.receipt])
                    rows = sorted((r for r in available if start <= r['updated_timestamp'] <= end),
                                  key=lambda r: (r['updated_timestamp'], r['receipt_id']))
                    return self.reply(200, {'count': len(rows), 'results': rows[offset:offset+limit]})
            except (ValueError, KeyError):
                self.reply(400, {})

    class Control(API):
        def do_POST(self):
            if handle_control(self, state):
                return
            if self.path != '/control':
                return self.reply(404, {})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 10000:
                    raise ValueError('body limit')
                state.configure(json.loads(self.rfile.read(length)))
                self.reply(200, {'configured': True})
            except (ValueError, KeyError):
                self.reply(400, {})
    return API, Control


if __name__ == '__main__':
    api, control = handlers(State())
    threading.Thread(target=ThreadingHTTPServer(('0.0.0.0', 8081), control).serve_forever, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 80), api).serve_forever()
