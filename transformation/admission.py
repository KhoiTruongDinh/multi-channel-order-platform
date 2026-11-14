"""Short source registration fence shared by legacy and delta freeze paths."""
from transformation.source_config import SOURCES


def registration_lock(conn, source):
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                 (f'batch-registration:{source}:{SOURCES[source][0]}',))


def admit(conn, source, owner_workflow_id=None):
    registration_lock(conn, source)
    if conn.execute("SELECT to_regclass('ops.source_cycle_owners')").fetchone()[0] is None:
        return
    row = conn.execute('''SELECT o.run_id FROM ops.source_cycle_owners o
        JOIN ops.pipeline_runs p USING(run_id) WHERE o.source_system=%s
        AND o.source_account_id=%s AND p.status NOT IN ('SUCCEEDED','FAILED')''',
                       (source,SOURCES[source][0])).fetchone()
    if row and row[0] != owner_workflow_id:
        raise RuntimeError('nonterminal source owner must finish or be explicitly aborted before freeze')
