"""Read-only SQL/Python parity checks; fixture access is confined to test code."""
import json
import sys
from pathlib import Path

sys.path.insert(0, '/fixtures/s01')
from fixture_tools import canonical_business, fingerprint

from psycopg.types.json import Jsonb
from transformation.batch import connect

keys = ('orders', 'order_items', 'payment_transactions', 'cancellation_requests', 'shipments', 'shipment_items')
cases = [{}, {'a': None}, {'unknown': [1, 2]}, {'unknown': [2, 1]},
         {'label': 'Cốc gốm', 'nested': {'z': 1, 'a': 'x'}}]
for name in ('WEB_R1', 'WEB_R2', 'WEB_R3'):
    payload = json.loads((Path('/fixtures/s01/responses/internal_web') / f'{name}.json').read_text())
    cases.append({key: payload[key] for key in keys})

with connect() as connection:
    for payload in cases:
        actual, actual_hash = connection.execute(
            "SELECT build.canonical_jsonb_text(%s::jsonb), encode(sha256(convert_to(build.canonical_jsonb_text(%s::jsonb),'UTF8')),'hex')",
            (Jsonb(payload), Jsonb(payload)),
        ).fetchone()
        assert actual.encode() == canonical_business(payload, 'website_order')
        assert actual_hash == fingerprint(payload, 'website_order')
    observations = connection.execute(
        'SELECT business_payload, encode(content_fingerprint,\'hex\') FROM build.stg_website_observations'
    ).fetchall()
    for payload, actual_hash in observations:
        assert actual_hash == fingerprint(payload, 'website_order')
print(f'M03 website fingerprint parity PASS: {len(cases)} cases, {len(observations)} retained observations')
