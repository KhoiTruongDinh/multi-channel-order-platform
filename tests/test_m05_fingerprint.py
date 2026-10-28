"""Fixture utility parity for SQL eBay canonicalization; test-only fixture mount."""
import copy
import json
from pathlib import Path
import sys
from psycopg.types.json import Jsonb
from transformation.batch import connect

sys.path.insert(0,'/fixtures/s01')
from fixture_tools import canonical_business, fingerprint

cases = [{}, {'a':None}, {'unknown':[2,1]}, {'unknown':[1,2]}, {'unicode':'Cốc gốm'}]
for name in ('0902','0912'):
    value = json.loads((Path('/fixtures/s01/source_states/ebay') / (name+'.json')).read_text())
    cases.extend([value['order'], {'fulfillments':value['fulfillments']}])
    reversed_order = copy.deepcopy(value['order'])
    reversed_order['lineItems'].reverse()
    cases.append(reversed_order)
with connect() as conn:
    for value in cases:
        text, actual = conn.execute("SELECT build.canonical_jsonb_text(build.ebay_canonical_json(%s)),encode(sha256(convert_to(build.canonical_jsonb_text(build.ebay_canonical_json(%s)),'UTF8')),'hex')",(Jsonb(value),Jsonb(value))).fetchone()
        assert text.encode()==canonical_business(value,'ebay_order')
        assert actual==fingerprint(value,'ebay_order')
    for value in ({'lineItems':[{'lineItemId':'x'},{'lineItemId':'x'}]}, {'lineItems':[{}]}):
        try:
            with conn.transaction():
                conn.execute('SELECT build.ebay_canonical_json(%s)',(Jsonb(value),)).fetchone()
        except Exception:
            pass
        else:
            raise AssertionError('bad collection identity accepted')
print(f'M05 SQL/Python fingerprint parity PASS: {len(cases)} cases + 2 invalid collections')
