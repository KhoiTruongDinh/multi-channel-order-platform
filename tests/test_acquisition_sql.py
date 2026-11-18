"""Offline Jinja/lineage checks, NOT PostgreSQL execution or dbt parity."""
from pathlib import Path
import unittest
from jinja2 import Environment,StrictUndefined

ROOT=Path(__file__).resolve().parents[1]/'transformations'


def render(model,source):
    files=('canonical_jsonb.sql','ebay_canonical.sql','etsy.sql','delta.sql','etsy_cache.sql')
    macros='\n'.join((ROOT/'macros'/name).read_text() for name in files)
    env=Environment(undefined=StrictUndefined,extensions=['jinja2.ext.do'])
    values={'batch_id':'00000000-0000-4000-8000-000000000001','release_source':source,
            'mapping_version':'unit','transformation_version':'unit'}
    context={'var':lambda k,default=None:values.get(k,default),'config':lambda **kwargs:'',
             'source':lambda s,t:{'acquisition':'raw','operations':'ops','canonical_cache':'cache'}[s]+'.'+t,
             'ref':lambda n:'build.'+n,'return':lambda x:x,'local_md5':lambda x:'a'*32}
    return env.from_string(macros+'\n'+model).render(**context)


class SqlTests(unittest.TestCase):
    def test_legacy_cache_probe_renderer_handles_new_empty_element_branch(self):
        from tests.etsy_staging_probe import model_sql,cache_sql
        for sql in (model_sql(),cache_sql()):
            self.assertNotIn('{{',sql); self.assertNotIn('{%',sql)
            self.assertIn('probe_elements',sql)

    def test_ebay_keeps_raw_and_entity_in_shipping_parent_join(self):
        sql=render((ROOT/'models/ebay/stg_ebay_observations.sql').read_text(),'ebay_sim')
        self.assertNotIn('{{',sql)
        self.assertIn("f.metadata->>'order_raw_id'=r.raw_record_id::TEXT",sql)
        self.assertIn("coalesce(f.metadata->>'order_id',CASE WHEN r.order_kind='ebay_order'",sql)
        self.assertIn("r.parsed_payload->'orders'->e.element_index",sql)
        self.assertIn('ops.acquisition_elements',sql)

    def test_etsy_element_cache_never_keys_only_by_whole_page_hash(self):
        sql=render('{{ populate_etsy_cache() }}','etsy_sim')
        self.assertIn('INSERT INTO cache.etsy_payloads',sql)
        self.assertIn('INSERT INTO cache.etsy_elements',sql)
        self.assertIn('source_entity_id,element_sha256,normalization_version',sql)
        self.assertIn('Etsy element cache payload identity mismatch',sql)
        self.assertIn("r.parsed_payload->'results'->e.element_index",sql)

    def test_etsy_stage_consumes_both_real_detail_and_accepted_page_elements(self):
        sql=render((ROOT/'models/etsy/stg_etsy_observations.sql').read_text(),'etsy_sim')
        self.assertIn("r.resource_type='etsy_receipt'",sql)
        self.assertIn("r.resource_type='etsy_receipts'",sql)
        self.assertIn('UNION ALL',sql)

    def test_route_includes_only_accepted_etsy_pages(self):
        sql=render('{{ delta_route_sql() }}','etsy_sim')
        self.assertIn('ops.acquisition_elements',sql)
        self.assertIn("r.parsed_payload->'results'",sql)


if __name__=='__main__': unittest.main()
