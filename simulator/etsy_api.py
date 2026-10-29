"""Fixed Etsy HTTP subset; controls are test-only and on a separate listener."""
import json
import os
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.configure({})

    def configure(self, config):
        name = config.get('state', '0905')
        if name not in ('0904', '0905'):
            raise ValueError('unsupported state')
        with self.lock:
            self.receipt = json.loads((Path('/fixtures/etsy') / f'{name}.json').read_text())
            self.status = int(config.get('error_status', 500))
            self.errors = int(config.get('errors_left', 0))


def handlers(state):
    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, value):
            body = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            if status == 429:
                self.send_header('Retry-After', '1')
            self.end_headers()
            self.wfile.write(body)

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
                        return self.reply(200, state.receipt) if match[1] == str(state.receipt['receipt_id']) else self.reply(404, {})
                    q = parse_qs(parsed.query, strict_parsing=True)
                    if any(len(v) != 1 for v in q.values()) or set(q) != {'min_last_modified','max_last_modified','limit','offset','sort_on','sort_order'}:
                        raise ValueError('explicit query required')
                    start, end, limit, offset = (int(q[k][0]) for k in ('min_last_modified','max_last_modified','limit','offset'))
                    if start > end or not 1 <= limit <= 100 or offset < 0 or q['sort_on'] != ['updated'] or q['sort_order'] != ['asc']:
                        raise ValueError('invalid bounds or sort')
                    rows = [state.receipt] if start <= state.receipt['updated_timestamp'] <= end else []
                    return self.reply(200, {'count': len(rows), 'results': rows[offset:offset+limit]})
            except (ValueError, KeyError):
                self.reply(400, {})

    class Control(API):
        def do_POST(self):
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
