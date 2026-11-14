"""Bounded-day publication regressions; called only in the disposable harness."""
import copy


def check(plan, acquire, admin, cycle, template):
    with admin() as conn:
        assert conn.info.host.startswith('delta-pg-'), 'disposable scope required'

    def payload(identity, day, updated='2026-10-17T09:59:00Z', currency='USD'):
        value = copy.deepcopy(template)
        original = value['orders'][0]['order_id']
        for rows in value.values():
            for row in rows:
                if isinstance(row, dict) and row.get('order_id') == original:
                    row['order_id'] = identity
                if isinstance(row, dict) and 'currency' in row:
                    row['currency'] = currency
        value['orders'][0]['created_at'] = f'2026-10-{day:02d}T01:00:00Z'
        value['orders'][0]['updated_at'] = updated
        return value

    def rows(conn, date=None):
        result = []
        for table in ('order_activity_daily', 'product_activity_daily'):
            predicate = ' AND activity_date=%s' if date else ''
            args = (date,) if date else ()
            result += conn.execute(f'''SELECT %s,to_jsonb(t)::text FROM mart.{table} t
                WHERE source_system='internal_web' {predicate} ORDER BY to_jsonb(t)::text''',
                                   (table, *args)).fetchall()
        return result

    with admin() as conn:
        untouched = rows(conn, '2026-10-17')
    acquire('internal_web', payload('daily-keep', 1), 'website_order_window')
    acquire('internal_web', payload('daily-move', 2), 'website_order_window')
    cycle(plan)
    with admin() as conn:
        assert rows(conn, '2026-10-17') == untouched, 'untouched day/lineage changed'
        day1 = rows(conn, '2026-10-01')
    changed = payload('daily-move', 3, '2026-10-17T10:00:00Z', 'EUR')
    acquire('internal_web', changed, 'website_order_window')
    batch = cycle(plan)
    with admin() as conn:
        dates = conn.execute('''SELECT activity_date::text FROM build_delta_web.candidate_activity_scope
            WHERE batch_id=%s ORDER BY activity_date''', (batch,)).fetchall()
        assert dates == [('2026-10-02',), ('2026-10-03',)], dates
        assert not rows(conn, '2026-10-02'), 'empty former day was not deleted'
        assert rows(conn, '2026-10-01') == day1, 'unrelated day changed'
        assert rows(conn, '2026-10-17') == untouched, 'retained later day changed'
        assert conn.execute('''SELECT currency,order_count FROM mart.order_activity_daily
            WHERE source_system='internal_web' AND activity_date='2026-10-03' ''').fetchall() == [('EUR', 1)]
        before_empty = rows(conn)
    cycle(plan)
    with admin() as conn:
        assert rows(conn) == before_empty, 'empty tick rewrote daily values/lineage'
        assert conn.execute('SELECT count(*) FROM build_delta_web.candidate_activity_scope').fetchone()[0] == 0
    acquire('internal_web', changed, 'website_order_window')
    cycle(plan)
    with admin() as conn:
        assert rows(conn) == before_empty, 'replay duplicated counts or rewrote untouched measures'
    acquire('internal_web', payload('daily-late', 1), 'website_order_window')
    cycle(plan)
    with admin() as conn:
        assert conn.execute('''SELECT order_count FROM mart.order_activity_daily
            WHERE source_system='internal_web' AND activity_date='2026-10-01' ''').fetchone()[0] == 2
        assert rows(conn, '2026-10-17') == untouched
    return dict(status='PASS', checks=['old-and-new-day-scope', 'empty-former-day-removal',
        'currency-change', 'untouched-day-values-and-lineage', 'empty-tick-no-daily-rewrite',
        'duplicate-version-no-inflation', 'late-old-day-not-current-date'])
