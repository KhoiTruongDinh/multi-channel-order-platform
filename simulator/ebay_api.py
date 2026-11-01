"""Fixed local eBay subset. Test controls are served on a separate listener."""
import copy
import json
import os
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit
from simulator.s02_store import Store, control as handle_control
from simulator.s02_temporal import make_store, PostgresStore, LivePostgresStore
from simulator.http_faults import Faults

ROOT = '/sell/fulfillment/v1/order'


class State:
    def __init__(self, fixtures):
        self.fixtures = Path(fixtures)
        self.lock = threading.Lock()
        self.s02 = make_store('ebay')
        self.configure({'state': '0912'})

    def configure(self, value):
        faults = Faults(value.get('transport_fault'))
        name = value.get('state', '0912')
        if name not in ('0902', '0912'):
            raise ValueError('unsupported source state')
        with self.lock:
            self.data = (json.loads((self.fixtures / f'{name}.json').read_text())
                         if self.s02 is None else {})
            self.repeat = bool(value.get('repeat_page', False))
            self.extra_order = bool(value.get('extra_order', False))
            self.bad_next = bool(value.get('bad_next', False))
            self.fail_offset = value.get('fail_offset')
            self.error_status = int(value.get('error_status', 500))
            self.errors_left = int(value.get('errors_left', 0))
            self.faults = faults


def handlers(state):
    class API(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log Authorization or URL query credentials.

        def send_json(self, status, value):
            broken = state.faults.response(self.path, status)
            raw = broken if broken is not None else json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            if status == 429:
                self.send_header('Retry-After', '0')
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Expected when the timeout test client has disconnected.

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
            if split.path=='/s02/clock' and not query and isinstance(state.s02,PostgresStore) and not isinstance(state.s02,LivePostgresStore):
                return self.send_json(200,state.s02.clock())
            if state.s02 is not None:
                return self.serve_s02(split, query)
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

        def serve_s02(self, split, query):
            from datetime import datetime
            if split.path == ROOT:
                match = re.fullmatch(r'lastmodifieddate:\[(.+)\.\.(.+)\]', query.get('filter', [''])[0])
                if not match or set(query) - {'filter', 'limit', 'offset'} or any(len(v) != 1 for v in query.values()):
                    raise ValueError('bounded filter required')
                start, end = (datetime.fromisoformat(x.replace('Z', '+00:00')) for x in match.groups())
                limit, offset = int(query.get('limit', ['50'])[0]), int(query.get('offset', ['0'])[0])
                if offset == state.fail_offset and state.errors_left > 0:
                    state.errors_left -= 1
                    return self.send_json(state.error_status, {'error': 'intentional test fault'})
                if start.tzinfo is None or end.tzinfo is None or start > end or not 1 <= limit <= 200 or offset < 0:
                    raise ValueError('invalid bounds/page')
                if isinstance(state.s02, PostgresStore):
                    # Deliberately repeat the first logical order for a named
                    # test only; ordinary live pages are unchanged.
                    at = max(0, offset - 1) if state.repeat and offset else offset
                    size = max(1,limit-1) if state.repeat and offset == 0 else limit
                    values, total = state.s02.query(start=start,end=end,limit=size,offset=at)
                    if state.repeat and total:
                        total += 1
                        if offset == 0 and limit > 1:
                            values = [values[0], *values][:limit]
                    rows = [v['order'] for v in values]
                else:
                    ordered = sorted(state.s02.rows.values(), key=lambda v: (state.s02.identity(v)[1], v['order']['orderId']))
                    available = [copy.deepcopy(v['order']) for v in ordered if start <= state.s02.identity(v)[1] <= end]
                    total, rows = len(available), available[offset:offset+limit]
                for row in rows:
                    row['cancelStatus']['cancelRequests'] = []
                def href(at):
                    return os.environ.get('EBAY_PUBLIC_ORIGIN', 'http://ebay-sim') + ROOT + '?' + urlencode(
                        dict(filter=query['filter'][0], limit=limit, offset=at))
                result = dict(orders=rows, total=total, limit=limit, offset=offset, href=href(offset))
                if offset + limit < total:
                    result['next'] = 'http://untrusted.invalid/steal' if state.bad_next else href(offset + limit)
                if offset:
                    result['prev'] = href(max(0, offset-limit))
                return self.send_json(200, result)
            if isinstance(state.s02, PostgresStore):
                match = re.fullmatch(re.escape(ROOT)+r'/([^/]+)(?:/shipping_fulfillment(?:/([^/]+))?)?',split.path)
                if not match or query:
                    return self.send_json(404, {'error':'not found'})
                value = state.s02.get(match[1])
                candidates = [(match[1],value)] if value else []
            else:
                candidates = state.s02.rows.items()
            for identity, value in candidates:
                path = ROOT + '/' + identity
                if split.path == path and not query:
                    return self.send_json(200, value['order'])
                if split.path == path + '/shipping_fulfillment' and not query:
                    return self.send_json(200, dict(total=len(value['fulfillments']), fulfillments=value['fulfillments']))
                for fulfillment in value['fulfillments']:
                    if split.path == path + '/shipping_fulfillment/' + fulfillment['fulfillmentId'] and not query:
                        return self.send_json(200, fulfillment)
            return self.send_json(404, {'error': 'not found'})

    class Control(API):
        def do_GET(self):
            self.send_json(404, {'error': 'test control only'})

        def do_POST(self):
            if handle_control(self, state):
                return
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
