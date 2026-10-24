"""Offline fixture utilities. Not a running ingestion pipeline or vendor SDK."""
import base64
import copy
import hashlib
import hmac
import json
from datetime import datetime, timezone

TEST_SECRET = b'S01_PUBLIC_TEST_KEY_NOT_A_SECRET!'
TOLERANCE_SECONDS = 300


def utc_seconds(value):
    if isinstance(value, (int, float)):
        return int(value)
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp())


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def sign(message_id, timestamp, raw_body, secret=TEST_SECRET):
    signed = f'{message_id}.{timestamp}.'.encode() + raw_body
    return 'v1,' + base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode()


def verify_signature(headers, raw_body, received_at, secret=TEST_SECRET):
    """Use injected fixture/delivery time, never bypass freshness validation."""
    timestamp = int(headers['webhook-timestamp'])
    if abs(utc_seconds(received_at) - timestamp) > TOLERANCE_SECONDS:
        raise ValueError('Webhook timestamp outside allowed tolerance')
    expected = sign(headers['webhook-id'], timestamp, raw_body, secret)
    if not any(hmac.compare_digest(expected, entry)
               for entry in headers['webhook-signature'].split()):
        raise ValueError('Invalid webhook signature')


def canonical_business(payload, kind):
    """Only caller-supplied business object; acquisition metadata stays outside.

    Known unordered collections use source identifiers. Unknown arrays preserve
    order. Null and absent fields remain different. Conflicting aliases fail.
    """
    value = copy.deepcopy(payload)
    if kind == 'etsy_receipt':
        for alias, main in [('create_timestamp', 'created_timestamp'),
                            ('update_timestamp', 'updated_timestamp')]:
            if alias in value:
                if main in value and value[main] != value[alias]:
                    raise ValueError(f'Conflicting timestamp alias: {alias}')
                value[main] = value.pop(alias)
    keys = {'lineItems': 'lineItemId', 'transactions': 'transaction_id',
            'fulfillments': 'fulfillmentId'}

    def normalize(node):
        if isinstance(node, dict):
            result = {}
            for key, child in node.items():
                child = normalize(child)
                if key in keys and isinstance(child, list):
                    identity = keys[key]
                    if not all(isinstance(x, dict) and identity in x for x in child):
                        raise ValueError(f'Missing stable collection identity: {key}')
                    ids = [str(x[identity]) for x in child]
                    if len(ids) != len(set(ids)):
                        raise ValueError(f'Duplicate collection identity: {key}')
                    child = sorted(child, key=lambda x: str(x[identity]))
                result[key] = child
            return result
        if isinstance(node, list):
            return [normalize(x) for x in node]
        return node

    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def fingerprint(payload, kind):
    return hashlib.sha256(canonical_business(payload, kind)).hexdigest()


def resolve_mapping(mappings, source, account, listing=None, variant=None, sku=None):
    """Exact scoped references first; unique SKU fallback; conflicts fail."""
    scoped = [m for m in mappings if m['source_system'] == source
              and m['source_account_id'] == str(account)]
    by_id = [m for m in scoped if variant is not None
             and m['source_variant_id'] == str(variant)
             and (listing is None or m['source_listing_id'] == str(listing))]
    by_sku = [m for m in scoped if sku is not None and m['source_sku'] == sku]
    candidates = by_id or by_sku
    if not candidates:
        raise ValueError('Unmapped source product')
    if len(candidates) != 1:
        raise ValueError('Ambiguous source product mapping')
    if by_id and by_sku and (len(by_sku) != 1 or
                            by_sku[0]['canonical_variant_id'] != by_id[0]['canonical_variant_id']):
        raise ValueError('Conflicting source product identifiers')
    return candidates[0]['canonical_variant_id']
