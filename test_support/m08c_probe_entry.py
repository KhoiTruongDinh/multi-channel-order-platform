"""Test-controller-only signing key; never added to the Airflow service environment."""
import os
from pathlib import Path
import runpy
import sys


def main():
    values = dict(line.split('=', 1) for line in Path('/m08c/private.env').read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    os.environ['ETSY_SIGNING_SECRET'] = values['ETSY_SIGNING_SECRET']
    target, *arguments = sys.argv[1:]
    sys.argv = [target, *arguments]
    if target.endswith('.py'):
        runpy.run_path(target, run_name='__main__')
    else:
        runpy.run_module(target, run_name='__main__')


if __name__ == '__main__':
    main()
