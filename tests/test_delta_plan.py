"""Offline compiled-plan identity tests; not SQL/runtime acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from transformation import delta_plan as p


class PlanTests(unittest.TestCase):
    def plan(self):
        value = dict(format=1,source='internal_web',schema='build_delta_web',source_hash='source',
                     models=[dict(id='model.project.example',name='example',
                                  relation='"data_platform"."build_delta_web"."example"',sql='SELECT 1')],
                     tests=[dict(id='test.project.example',sql='SELECT 1 WHERE FALSE')])
        value['plan_sha256'] = p.digest(value)
        return value

    def signed(self, **changes):
        value = self.plan()
        value.pop('plan_sha256')
        value.update(changes)
        value['plan_sha256'] = p.digest(value)
        return value

    def test_valid_owned_plan(self):
        with patch.object(p,'source_hash',return_value='source'):
            self.assertEqual(p.validate(self.plan())['source'],'internal_web')

    def test_changed_sql_refuses(self):
        value = copy.deepcopy(self.plan())
        value['models'][0]['sql'] = 'SELECT 2'
        with patch.object(p,'source_hash',return_value='source'), self.assertRaises(ValueError):
            p.validate(value)

    def test_changed_source_refuses(self):
        with patch.object(p,'source_hash',return_value='new-source'), self.assertRaises(ValueError):
            p.validate(self.plan())

    def test_wrong_source_schema_refuses(self):
        with patch.object(p,'source_hash',return_value='source'), self.assertRaises(ValueError):
            p.validate(self.signed(schema='build_delta_etsy'))

    def test_unrelated_relation_refuses(self):
        value = self.plan()['models']
        value[0]['relation'] = '"data_platform"."core"."orders_current"'
        with patch.object(p,'source_hash',return_value='source'), self.assertRaises(ValueError):
            p.validate(self.signed(models=value))

    def test_empty_quality_gate_refuses(self):
        with patch.object(p,'source_hash',return_value='source'), self.assertRaises(ValueError):
            p.validate(self.signed(tests=[]))

    def test_duplicate_gate_node_refuses(self):
        nodes = self.plan()['tests'] * 2
        with patch.object(p,'source_hash',return_value='source'), self.assertRaises(ValueError):
            p.validate(self.signed(tests=nodes))

    def test_generated_artifacts_are_not_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'transformations/target/batch').mkdir(parents=True)
            (root/'transformation').mkdir()
            for name in ('delta_plan.py','delta_runtime.py','delta_publish.py','source_config.py','admission.py'):
                (root/'transformation'/name).write_text('# synthetic test source')
            model = root/'transformations/model.sql'
            model.write_text('SELECT 1')
            artifact = root/'transformations/target/batch/generated.sql'
            artifact.write_text('SELECT 2')
            with patch.object(p,'ROOT',root):
                original = p.source_hash()
                artifact.write_text('SELECT 3')
                self.assertEqual(original,p.source_hash())
                model.write_text('SELECT 4')
                self.assertNotEqual(original,p.source_hash())
                (root/'transformations/models/target').mkdir(parents=True)
                nested = root/'transformations/models/target/business.sql'
                nested.write_text('SELECT 5')
                previous = p.source_hash()
                nested.write_text('SELECT 6')
                self.assertNotEqual(previous,p.source_hash())

    def test_unsupported_dbt_features_refuse(self):
        for config in (dict(materialized='incremental'),
                       dict(materialized='table',contract=dict(enforced=True)),
                       {'materialized':'table','post-hook':['SELECT 1']}):
            with self.assertRaises(ValueError):
                p.check_model_config(dict(name='example',config=config))
        p.check_model_config(dict(name='example',config=dict(materialized='table')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
