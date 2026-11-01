"""Actual compiled dbt SQL with literal bad inputs; no candidate/source mutation."""
import copy
import json
from pathlib import Path
import re
import uuid

from psycopg.types.json import Jsonb
from transformation.batch import connect
from orchestration.website_workflow import ROOT


def main():
    fixture = json.loads(Path('/repo/fixtures/s01/source_states/website/0901.json').read_text())
    with connect() as conn:
        batch = conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='website_orders'").fetchone()[0]
        directory = ROOT / 'transformations/target' / str(batch) / 'compiled/multi_channel_orders/models/candidates'
        header = (directory / 'candidate_order_snapshot_history.sql').read_text()
        line = (directory / 'candidate_order_line_snapshot_history.sql').read_text()
        replacement = """(SELECT %s::jsonb AS order_json,%s::jsonb AS business_payload,%s::uuid AS snapshot_id,
            'internal_web'::text AS source_system,'WEB01'::text AS source_account_id,'W1001'::text AS source_order_id,
            '2026-10-17T09:00:00Z'::timestamptz AS source_created_at,
            '2026-10-17T09:01:00Z'::timestamptz AS source_updated_at,clock_timestamp() AS first_observed_at,
            decode(repeat('00',32),'hex') AS content_fingerprint)"""
        def literal(sql):
            result, count = re.subn(r'"[^"]+"\."build"\."int_website_versions"', replacement, sql)
            assert count == 1, 'compiled input reference changed'
            return result
        header, line = literal(header), literal(line)
        bad = copy.deepcopy(fixture)
        bad['orders'][0]['payment_status'] = 'TEST_UNKNOWN'
        key = uuid.uuid4()
        parameters = (Jsonb(bad['orders'][0]), Jsonb(bad), key)
        constraints = (ROOT / 'transformations/tests/website_constraints.sql').read_text()
        constraints = constraints.replace("{{ ref('candidate_order_snapshot_history') }}", 'headers')
        constraints = constraints.replace("{{ ref('candidate_order_line_snapshot_history') }}", 'lines')
        sql = 'WITH headers AS (' + header + '), lines AS (' + line + ') SELECT * FROM (' + constraints + ') failures'
        assert conn.execute(sql, parameters + parameters).fetchall(), 'unknown state escaped actual dbt constraint'
        missing = copy.deepcopy(fixture)
        for row in missing['order_items']:
            row['variant_id'] = 'M08C-MISSING'
            row['sku_at_purchase'] = 'M08C-MISSING'
        cursor = conn.execute(line, (Jsonb(missing['orders'][0]), Jsonb(missing), uuid.uuid4()))
        names = [column.name for column in cursor.description]
        lines = [dict(zip(names, row)) for row in cursor.fetchall()]
        assert lines and all(row['mapping_status'] == 'UNMAPPED' and row['canonical_variant_id'] is None for row in lines)
        conflict = (ROOT / 'transformations/tests/no_equal_time_conflicts.sql').read_text()
        conflict = conflict.replace("{{ ref('candidate_order_snapshot_history') }}", 'observations')
        observation = "SELECT 'internal_web'::text source_system,'WEB01'::text source_account_id,'C-CONFLICT'::text source_order_id,now() source_updated_at"
        assert conn.execute('WITH observations AS (' + observation + ' UNION ALL ' + observation + ') ' + conflict).fetchall()
    print(json.dumps(dict(status='PASS', scope='actual dbt compiled policy SQL, read-only literal inputs',
                          unknown_status='rejected', missing_mapping='UNMAPPED/no invented variant', equal_time='rejected')))


if __name__ == '__main__':
    main()
