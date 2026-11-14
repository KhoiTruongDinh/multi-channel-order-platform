"""Mapping release/rebootstrap acceptance; disposable PostgreSQL ONLY."""
from pathlib import Path
import time
import uuid


def check(old_plan,admin):
    from transformation.delta_plan import compile_plan,load
    from transformation.delta_runtime import source_lock,freeze,build
    from transformation.delta_publish import audited_publish
    with admin() as conn:
        host=conn.info.host
        assert host.startswith('delta-pg-'), 'never alter owner mappings in this probe'

    def identity(conn):
        return conn.execute('''SELECT snapshot_id,source_order_id,source_updated_at,
            first_observed_at,content_fingerprint FROM core.order_snapshot_history
            WHERE source_system='ebay_sim' ORDER BY snapshot_id''').fetchall()

    def raw_signature(conn):
        return conn.execute('''SELECT count(*),md5(string_agg(md5(to_jsonb(r)::text),''
            ORDER BY raw_record_id)) FROM raw.raw_records r''').fetchone()

    with admin() as conn:
        before=identity(conn); raw_before=raw_signature(conn)
        canonical={r[0] for r in conn.execute("SELECT canonical_variant_id FROM core.order_lines_current WHERE source_system='ebay_sim'")}
        pointer=conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='ebay_orders'").fetchone()[0]
        seen=conn.execute('SELECT count(*) FROM ops.delta_seen_raw').fetchone()[0]
        # Existing active unique indexes deliberately exclude mapping_version.
        # Close the previous release before opening its explicit replacement.
        conn.execute("UPDATE config.product_mapping SET valid_to=clock_timestamp() WHERE source_system='ebay_sim' AND mapping_version='s01-v1' AND valid_to IS NULL")
        conn.execute('''INSERT INTO config.product_mapping
            (mapping_id,mapping_version,source_system,source_account_id,source_listing_id,
             source_variant_id,source_sku,canonical_variant_id,mapping_status,valid_from,created_at)
            SELECT gen_random_uuid(),'delta-map-v2',source_system,source_account_id,source_listing_id,
             source_variant_id,source_sku,'REMAP-'||canonical_variant_id,mapping_status,
             clock_timestamp(),clock_timestamp() FROM config.product_mapping
            WHERE source_system='ebay_sim' AND mapping_version='s01-v1' ''')
    try:
        with source_lock(old_plan) as conn:
            freeze(conn,old_plan,uuid.uuid4(),uuid.uuid4())
    except RuntimeError as error:
        assert 'mapping changed' in str(error)
    else:
        raise AssertionError('stale mapping plan accepted')
    with admin() as conn:
        assert identity(conn)==before and raw_signature(conn)==raw_before
        assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw').fetchone()[0]==seen
        assert conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='ebay_orders'").fetchone()[0]==pointer

    path=Path('/tmp/delta-plans/ebay-map-v2.json')
    compile_plan('ebay_sim','delta-map-v2','delta-rebootstrap-v2',path)
    plan=load(path)
    try:
        with source_lock(plan) as conn:
            freeze(conn,plan,uuid.uuid4(),uuid.uuid4())
    except RuntimeError as error:
        assert 'bootstrap is required' in str(error)
    else:
        raise AssertionError('new plan skipped explicit bootstrap')
    batch=uuid.uuid4(); start=time.monotonic()
    from transformation.delta_bootstrap import verified_bootstrap
    oracle=verified_bootstrap(plan,batch,uuid.uuid4(),uuid.uuid4())
    with admin() as conn:
        assert identity(conn)==before, 'mapping reprocessing changed source version identity'
        assert raw_signature(conn)==raw_before, 'mapping reprocessing changed raw acquisition audit'
        actual={r[0] for r in conn.execute("SELECT canonical_variant_id FROM core.order_lines_current WHERE source_system='ebay_sim'")}
        assert actual=={'REMAP-'+value for value in canonical},(canonical,actual)
        assert conn.execute("SELECT DISTINCT mapping_version,transformation_version FROM core.order_snapshot_history WHERE source_system='ebay_sim'").fetchall()==[('delta-map-v2','delta-rebootstrap-v2')]
        assert conn.execute("SELECT batch_id FROM ops.publication_state WHERE publication_name='ebay_orders'").fetchone()[0]==batch
        inputs=conn.execute('SELECT count(*) FROM ops.delta_new_inputs WHERE batch_id=%s',(batch,)).fetchone()[0]
        assert inputs>0
        assert conn.execute('SELECT count(*) FROM ops.delta_seen_raw WHERE processed_batch_id=%s',(batch,)).fetchone()[0]==inputs
    # A warm no-input cycle after explicit rebootstrap retains the new release.
    empty=uuid.uuid4()
    with source_lock(plan) as conn:
        freeze(conn,plan,empty,uuid.uuid4()); build(conn,plan,empty)
        audited_publish(plan,empty,uuid.uuid4())
    with admin() as conn:
        assert identity(conn)==before and raw_signature(conn)==raw_before
        assert conn.execute('SELECT count(*) FROM ops.delta_new_inputs WHERE batch_id=%s',(empty,)).fetchone()[0]==0
        # Even restoring the old config hash must NOT silently reactivate an
        # already-consumed old artifact over a newer publication/mapping.
        conn.execute("UPDATE config.product_mapping SET valid_to=clock_timestamp() WHERE source_system='ebay_sim' AND mapping_version='delta-map-v2' AND valid_to IS NULL")
        conn.execute("UPDATE config.product_mapping SET valid_to=NULL WHERE source_system='ebay_sim' AND mapping_version='s01-v1'")
    try:
        with source_lock(old_plan) as conn:
            freeze(conn,old_plan,uuid.uuid4(),uuid.uuid4())
    except RuntimeError as error:
        assert 'active publication uses another plan' in str(error)
    else:
        raise AssertionError('old already-consumed plan was silently reactivated')
    return dict(status='PASS',scope='private mapping transition after full dbt oracle; not owner activation',
        bootstrap=str(batch),retained_source_snapshots=len(before),reprocessed_raw=inputs,
        cold_seconds=time.monotonic()-start,full_dbt_oracle=oracle['full_dbt_oracle'],
        checks=['stale-plan-refused-with-last-good-intact','new-plan-requires-bootstrap',
                'same-source-snapshot-IDs-fingerprints-first-observation',
                'raw-acquisition-audit-unchanged','new-canonical-mapping-and-transformation-version',
                'exact-consumption-after-atomic-publication','post-bootstrap-no-input-idempotency',
                'old-artifact-refused-even-after-old-config-hash-restored'])
