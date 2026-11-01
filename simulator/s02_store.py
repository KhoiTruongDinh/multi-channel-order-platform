"""Opt-in bounded current-state store; never contains warehouse expectations."""
import copy
import hmac
import json
import os
from datetime import datetime


class Store:
    def __init__(self, kind):
        self.kind, self.rows = kind, {}

    def identity(self, value):
        if self.kind == 'ebay':
            order = value['order']
            identity = order['orderId']
            stamp = datetime.fromisoformat(order['lastModifiedDate'].replace('Z', '+00:00'))
            if not isinstance(identity, str) or not identity or stamp.tzinfo is None:
                raise ValueError('invalid eBay identity/time')
            if order['sellerId'] != 'seller_sim_01' or not isinstance(value['fulfillments'], list):
                raise ValueError('invalid seller/fulfillments')
        else:
            identity, stamp = value['receipt_id'], value['updated_timestamp']
            if type(identity) is not int or identity <= 0 or type(stamp) is not int or stamp <= 0:
                raise ValueError('invalid Etsy identity/time')
            if value['seller_user_id'] != 7001001 or not isinstance(value['transactions'], list):
                raise ValueError('invalid seller/transactions')
        return str(identity), stamp

    def upsert(self, value):
        identity, stamp = self.identity(value)
        previous = self.rows.get(identity)
        if previous:
            old = self.identity(previous)[1]
            if stamp < old or (stamp == old and value != previous):
                raise ValueError('backward/conflicting source version')
        if identity not in self.rows and len(self.rows) >= 100:
            raise ValueError('finite store limit')
        self.rows[identity] = copy.deepcopy(value)
        return {'committed': True, 'identity': identity}


def control(handler, state):
    """Return True only for the separate S02 control path. Caller supplies lock."""
    if handler.path != '/s02/upsert':
        return False
    reply = getattr(handler, 'send_json', None) or handler.reply
    token = os.environ.get('S02_CONTROL_TOKEN', '')
    if not isinstance(state.s02, Store) or not token or not hmac.compare_digest(
            handler.headers.get('X-S02-Control-Token', ''), token):
        reply(403, {'error': 'S02 control disabled/unauthorized'})
        return True
    try:
        length = int(handler.headers.get('Content-Length', '0'))
        if not 0 < length <= 1048576:
            raise ValueError('body limit')
        value = json.loads(handler.rfile.read(length))
        with state.lock:
            result = state.s02.upsert(value)
        reply(200, result)
    except (ValueError, KeyError, TypeError, AttributeError):
        reply(400, {'error': 'invalid S02 source document'})
    return True
