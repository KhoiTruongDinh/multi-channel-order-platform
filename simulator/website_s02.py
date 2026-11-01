"""Bounded append/update S02 source transaction; no warehouse/ledger access."""
import json
import sys
from psycopg import sql
import psycopg
from simulator.website_playback import TABLES, connection_kwargs, validate


def main():
    body = sys.stdin.read(1048577)
    if len(body.encode()) > 1048576:
        raise ValueError('S02 source body limit')
    data = json.loads(body)
    apply(data)
    print('S02 website source transaction committed')


def apply(data):
    validate(data)
    if len(data['orders']) != 1 or len(data['order_items']) > 10:
        raise ValueError('bounded single order transaction required')
    keys = dict(customers='customer_id', products='product_id', product_variants='variant_id',
        orders='order_id', order_items='order_item_id', payment_transactions='payment_transaction_id',
        shipments='shipment_id', cancellation_requests='cancellation_id')
    with psycopg.connect(**connection_kwargs()) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext('s02-website-writer'))")
        row = data['orders'][0]
        prior = conn.execute('SELECT updated_at FROM orders WHERE order_id=%s', (row['order_id'],)).fetchone()
        if prior:
            from datetime import datetime
            if datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) <= prior[0]:
                raise ValueError('S02 updates must strictly advance source time')
        from psycopg.types.json import Jsonb
        for table in TABLES:
            for values in data[table]:
                columns = list(values)
                key = keys.get(table)
                if not key:
                    raise ValueError('shipment allocation requires separate scenario')
                updates = [c for c in columns if c != key]
                query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
                    sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)),
                    sql.SQL(',').join(sql.Placeholder() for _ in columns), sql.Identifier(key),
                    sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c), sql.Identifier(c)) for c in updates))
                conn.execute(query, [Jsonb(v) if isinstance(v, (dict,list)) else v for v in values.values()])


if __name__ == '__main__':
    main()
