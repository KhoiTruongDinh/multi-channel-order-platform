{{ config(pre_hook="{{ populate_etsy_cache() }}") }}
-- Keep every acquisition and frozen membership; cache only the pure computation.
SELECT r.raw_record_id, r.run_id, r.source_system, r.source_account_id, r.acquired_at, r.byte_sha256, r.parsed_payload,c.order_json,c.content_fingerprint
  FROM ({{ etsy_cache_inputs() }}) r
  INNER JOIN {{ source('canonical_cache','etsy_payloads') }} c
    ON (c.source_system,c.source_account_id,c.byte_sha256,c.normalization_version)=
       (r.source_system,r.source_account_id,r.byte_sha256,'{{ etsy_cache_version() }}')
UNION ALL
SELECT r.raw_record_id,r.run_id,r.source_system,r.source_account_id,r.acquired_at,
       r.byte_sha256,r.parsed_payload,c.order_json,c.content_fingerprint
  FROM ({{ etsy_element_inputs() }}) r
  INNER JOIN {{ source('canonical_cache','etsy_elements') }} c
    ON (c.source_system,c.source_account_id,c.source_entity_id,c.element_sha256,c.normalization_version)=
       (r.source_system,r.source_account_id,r.source_entity_id,r.element_sha256,'{{ etsy_cache_version() }}')
