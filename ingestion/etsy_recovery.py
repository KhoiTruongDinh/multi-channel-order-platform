"""Durable, bounded scan identity; no business normalization or simulator access."""


class PageSetChanged(ValueError):
    pass


def begin_scan(conn, run):
    # The caller holds the existing collection-run advisory lock.
    row = conn.execute('''SELECT scan_number,status FROM ops.etsy_recovery_scans
        WHERE run_id=%s ORDER BY scan_number DESC LIMIT 1''', (run,)).fetchone()
    if row and row[1] != 'INVALID':
        return row
    number = row[0] + 1 if row else 1
    if number > 5:
        raise RuntimeError('recovery scan budget exhausted; controlled replay required')
    conn.execute('''INSERT INTO ops.etsy_recovery_scans(run_id,scan_number)
        VALUES(%s,%s)''', (run, number))
    conn.commit()
    return number, 'RUNNING'


def finish_scan(conn, run, number, valid):
    conn.execute('''UPDATE ops.etsy_recovery_scans SET status=%s,
        finished_at=GREATEST(clock_timestamp(),started_at),error_code=%s
        WHERE run_id=%s AND scan_number=%s AND status='RUNNING' ''',
        ('VALIDATED' if valid else 'INVALID', None if valid else 'PAGE_SET_CHANGED', run, number))
    conn.commit()


def page_history(conn, run, url, number):
    # Count ALL prior scans, not just cache-eligible rows. Never reset HTTP budget.
    rows = conn.execute('''SELECT r.response_status,r.parsed_payload,r.raw_record_id,
        a.recovery_scan_number,octet_length(r.raw_bytes) FROM ops.etsy_http_attempts a
        JOIN raw.raw_records r USING(raw_record_id)
        WHERE a.run_id=%s AND a.work_id IS NULL AND r.resource_locator=%s
        ORDER BY a.recorded_at DESC,a.attempt_id DESC''', (run, url)).fetchall()
    if len(rows) > 5:
        raise RuntimeError('invalid persisted recovery HTTP budget')
    cached = next((r for r in rows if r[3] == number or (number == 1 and r[3] is None)), None)
    return len(rows), cached
