"""Authored dbt SQL conventions; not a runtime performance or parity test."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DbtSqlStyleTests(unittest.TestCase):
    def test_explicit_projections_counts_joins_and_deduplication(self):
        files = sorted((ROOT / 'transformations').glob('models/**/*.sql'))
        files += sorted((ROOT / 'transformations').glob('macros/*.sql'))
        files += sorted((ROOT / 'transformations').glob('tests/*.sql'))
        self.assertTrue(files)
        for path in files:
            text = re.sub(r'--[^\n]*', '', path.read_text(encoding='utf-8'))
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertNotRegex(text, r'(?i)\bSELECT\s+\*|\b[a-z_]\w*\.\*')
                self.assertNotRegex(text, r'(?i)\bCOUNT\s*\(\s*\*\s*\)')
                self.assertNotRegex(text, r'(?i)\bSELECT\s+DISTINCT\b|\bCOUNT\s*\(\s*DISTINCT\b')
                self.assertNotRegex(text, r'(?i)\bTOP\s*\(')
                sql_text = re.sub(r'\{\{.*?\}\}|\{%.*?%\}', '', text, flags=re.S)
                for match in re.finditer(r'(?i)\bJOIN\b', sql_text):
                    self.assertRegex(sql_text[:match.start()], r'(?i)\b(INNER|LEFT|RIGHT|FULL|CROSS|OUTER)\s+$')

    def test_effective_current_requires_a_consumer_projection(self):
        macro = (ROOT / 'transformations/macros/delta.sql').read_text(encoding='utf-8')
        self.assertIn('effective_current(candidate, table, columns, order_scope=none)', macro)
        self.assertIn('for column in columns', macro)
        for path in (ROOT / 'transformations/models').rglob('*.sql'):
            for call in re.findall(r'effective_current\(([^)]*)\)', path.read_text(encoding='utf-8')):
                with self.subTest(path=path.name, call=call):
                    self.assertIn('[', call)


if __name__ == '__main__':
    unittest.main()
