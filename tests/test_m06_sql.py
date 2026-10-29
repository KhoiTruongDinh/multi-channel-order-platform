"""Read-only SQL/Python canonical parity and rollback-only Money rejection tests."""
import copy
import json
from pathlib import Path
import sys

from psycopg.types.json import Jsonb
from transformation.batch import connect

ROOT=Path('/repo')
sys.path.insert(0,str(ROOT/'fixtures/s01'))
from fixture_tools import fingerprint

base=json.loads((ROOT/'fixtures/s01/source_states/etsy/0905.json').read_text())
cases=[base]
alias=copy.deepcopy(base)
alias['update_timestamp']=alias['updated_timestamp']
alias['create_timestamp']=alias['created_timestamp']
cases.append(alias)
nullable=copy.deepcopy(base)
for key in ('listing_id','product_id','sku','title'):
    nullable['transactions'][0][key]=None
cases.append(nullable)
missing=copy.deepcopy(nullable)
del missing['transactions'][0]['title']
cases.append(missing)
extra=copy.deepcopy(base)
extra['transactions'].append(dict(extra['transactions'][0],transaction_id=8001002))
cases.append(extra)
cases.append(dict(extra,transactions=list(reversed(extra['transactions']))))
with connect() as c:
    for value in cases:
        actual=c.execute("SELECT encode(sha256(convert_to(build.canonical_jsonb_text(build.etsy_canonical_json(%s::JSONB)),'UTF8')),'hex')",(Jsonb(value),)).fetchone()[0]
        assert actual==fingerprint(value,'etsy_receipt'),(actual,fingerprint(value,'etsy_receipt'))
    for divisor,expected in ((100,22),(1000,2.2),(1,2200)):
        value=c.execute('SELECT build.etsy_money(%s::JSONB)',(Jsonb({'amount':2200,'divisor':divisor,'currency_code':'USD'}),)).fetchone()[0]
        assert str(value).startswith(str(expected)),value
    invalids=[dict(base,update_timestamp=0)]
    duplicate=copy.deepcopy(base)
    duplicate['transactions']*=2
    invalids.append(duplicate)
    for value,expected in zip(invalids,('Conflicting Etsy timestamp alias','collection identity')):
        try:
            with c.transaction():
                c.execute('SELECT build.etsy_canonical_json(%s::JSONB)',(Jsonb(value),))
        except Exception as error:
            assert expected in str(error),str(error)
        else:
            raise AssertionError('Invalid canonical input accepted')
    for value in ({'amount':1,'divisor':0,'currency_code':'USD'}, {'amount':1,'currency_code':'USD'}):
        try:
            with c.transaction():
                c.execute('SELECT build.etsy_money(%s::JSONB)',(Jsonb(value),))
        except Exception as error:
            assert 'Invalid Etsy Money' in str(error),str(error)
        else:
            raise AssertionError('Invalid Money accepted')
print('M06 SQL parity PASS: 6 canonical cases, 3 divisors, 4 invalid cases')
