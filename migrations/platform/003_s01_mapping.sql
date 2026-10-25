\set ON_ERROR_STOP on
BEGIN;

INSERT INTO config.product_mapping (
    mapping_id, mapping_version, source_system, source_account_id,
    source_listing_id, source_variant_id, source_sku, canonical_variant_id,
    mapping_status, valid_from, valid_to, created_at
) VALUES
    ('00000000-0000-4000-8000-000000000001', 's01-v1', 'internal_web', 'WEB01', NULL, 'V001', 'MUG-BLUE-350', 'V001', 'CONFIRMED', '2026-10-17T00:00:00Z', NULL, '2026-10-17T00:00:00Z'),
    ('00000000-0000-4000-8000-000000000002', 's01-v1', 'ebay_sim', 'seller_sim_01', '510001', '610001', 'EB-BLUE-350', 'V001', 'CONFIRMED', '2026-10-17T00:00:00Z', NULL, '2026-10-17T00:00:00Z'),
    ('00000000-0000-4000-8000-000000000003', 's01-v1', 'ebay_sim', 'seller_sim_01', '510001', '610002', 'EB-WHITE-350', 'V002', 'CONFIRMED', '2026-10-17T00:00:00Z', NULL, '2026-10-17T00:00:00Z'),
    ('00000000-0000-4000-8000-000000000004', 's01-v1', 'etsy_sim', '7001', '520001', '620002', 'ET-WHITE-350', 'V002', 'CONFIRMED', '2026-10-17T00:00:00Z', NULL, '2026-10-17T00:00:00Z')
ON CONFLICT (mapping_id) DO NOTHING;

INSERT INTO public.schema_migrations (migration_name)
VALUES ('platform/003_s01_mapping.sql') ON CONFLICT DO NOTHING;
COMMIT;
