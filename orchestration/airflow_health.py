"""Lightweight live-standalone readiness; no Airflow CLI import per probe."""
import json
from urllib.request import urlopen

URL='http://localhost:8080/api/v2/monitor/health'
REQUIRED=('metadatabase','scheduler','dag_processor')


def healthy(value):
    return isinstance(value,dict) and all(
        isinstance(value.get(name),dict) and value[name].get('status')=='healthy'
        for name in REQUIRED)


def main():
    try:
        with urlopen(URL,timeout=8) as response:
            value=json.load(response)
        if not healthy(value):
            print('Airflow database/scheduler/DAG processor not healthy')
            return 1
    except Exception as error:
        # Never echo a response body or credential-bearing exception text.
        print('Airflow readiness failed: '+type(error).__name__)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
