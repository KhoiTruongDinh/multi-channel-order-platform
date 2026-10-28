"""Fixed local eBay subset. Test controls are served on a separate listener."""
import copy
import json
import os
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = '/sell/fulfillment/v1/order'


class State:
    def __init__(self, fixtures):
        self.fixtures = Path(fixtures)
        self.lock = threading.Lock()
        self.configure({'state': '0912'})

    def configure(self, value):
        name = value.get('state', '0912')
        if name not in ('0902', '0912'):
            raise ValueError('unsupported source state')
        with self.lock:
            self.data = json.loads((self.fixtures / f'{name}.json').read_text())
            self.repeat = bool(value.get('repeat_page', False))
            self.extra_order = bool(value.get('extra_order', False))
            self.bad_next = bool(value.get('bad_next', False))
            self.fail_offset = value.get('fail_offset')
            self.error_status = int(value.get('error_status', 500))
            self.errors_left = int(value.get('errors_left', 0))


def handlers(state):
    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log Authorization or URL query credentials.

        def send_json(self, status, value):
            raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            if status == 429:
                self.send_header('Retry-After', '0')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == '/health':
                return self.send_json(200, {'status': 'ok'})
            if self.headers.get('Authorization') != 'Bearer ' + os.environ.get('EBAY_SIM_TOKEN', 'local-s01-test-token'):
                return self.send_json(401, {'error': 'unauthorized'})
            try:
                with state.lock:
                    return self.serve()
            except (ValueError, KeyError, TypeError):
                return self.send_json(400, {'error': 'invalid request'})

        def serve(self):
            split = urlsplit(self.path)
            query = parse_qs(split.query)
            data = state.data
            order = copy.deepcopy(data['order'])
            if state.extra_order and split.path.startswith(ROOT + '/12-10001-10002'):
                data = copy.deepcopy(data)
                data['order']['orderId'] = '12-10001-10002'
                data['order']['fulfillmentHrefs'] = [x.replace('12-10001-10001','12-10001-10002') for x in data['order']['fulfillmentHrefs']]
                order = data['order']
            if split.path == ROOT:
                match = re.fullmatch(r'lastmodifieddate:\[(.+)\.\.(.+)\]', query.get('filter', [''])[0])
                if not match or set(query) - {'filter', 'limit', 'offset'}:
                    raise ValueError('bounded lastmodifieddate required')
                from datetime import datetime
                start, end = (datetime.fromisoformat(x.replace('Z', '+00:00')) for x in match.groups())
                updated = datetime.fromisoformat(order['lastModifiedDate'].replace('Z', '+00:00'))
                if start.tzinfo is None or end.tzinfo is None or start > end:
                    raise ValueError('invalid bounds')
                limit, offset = int(query.get('limit', ['50'])[0]), int(query.get('offset', ['0'])[0])
                if not 1 <= limit <= 200 or offset < 0:
                    raise ValueError('invalid pagination')
                if offset == state.fail_offset and state.errors_left > 0:
                    state.errors_left -= 1
                    return self.send_json(state.error_status, {'error': 'intentional test fault'})
                rows = [order] * (2 if state.repeat else 1) if start <= updated <= end else []
                if rows and state.extra_order:
                    extra = copy.deepcopy(order)
                    extra['orderId'] = '12-10001-10002'
                    extra['fulfillmentHrefs'] = [x.replace('12-10001-10001','12-10001-10002') for x in extra['fulfillmentHrefs']]
                    rows.append(extra)
                order['cancelStatus']['cancelRequests'] = []
                def href(page_offset):
                    return os.environ.get('EBAY_PUBLIC_ORIGIN','http://ebay-sim') + ROOT + '?' + urlencode({
                        'filter': query['filter'][0], 'limit': limit, 'offset': page_offset})
                result = {'orders': rows[offset:offset + limit], 'total': len(rows),
                          'limit': limit, 'offset': offset, 'href': href(offset)}
                if offset + limit < len(rows):
                    result['next'] = 'http://untrusted.invalid/steal' if state.bad_next else href(offset + limit)
                if offset:
                    result['prev'] = href(max(0, offset - limit))
                return self.send_json(200, result)
            order_path = ROOT + '/' + order['orderId']
            if split.path == order_path and not query:
                return self.send_json(200, order)
            shipping = order_path + '/shipping_fulfillment'
            if split.path == shipping and not query:
                return self.send_json(200, {'total': len(data['fulfillments']), 'fulfillments': data['fulfillments']})
            for fulfillment in data['fulfillments']:
                if split.path == shipping + '/' + fulfillment['fulfillmentId'] and not query:
                    return self.send_json(200, fulfillment)
            return self.send_json(404, {'error': 'not found'})

    class Control(API):
        def do_GET(self):
            self.send_json(404, {'error': 'test control only'})

        def do_POST(self):
            if self.path != '/state':
                return self.send_json(404, {})
            try:
                state.configure(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_json(200, {'configured': True})
            except (ValueError, KeyError, TypeError):
                self.send_json(400, {'error': 'invalid test configuration'})
    return API, Control


if __name__ == '__main__':
    api, control = handlers(State(os.environ.get('EBAY_FIXTURE_ROOT', '/fixtures/ebay')))
    control_server = ThreadingHTTPServer(('0.0.0.0', 8081), control)
    threading.Thread(target=control_server.serve_forever, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 80), api).serve_forever()
