"""Optionally provision local SimpleAuthManager credentials from environment."""
import json
import os
from pathlib import Path
import re
import tempfile


def provision(path,username,password):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',username):
        raise ValueError('invalid local Airflow username')
    if not password:
        return  # Preserve the existing generated credential file.
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.loads(path.read_text()) if path.exists() else {}
    data[username]=password
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.passwords-')
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream)
        os.replace(name,path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


if __name__=='__main__':
    provision('/opt/airflow/state/passwords.json',os.environ.get('AIRFLOW_UI_USERNAME','admin'),
              os.environ.get('AIRFLOW_UI_PASSWORD',''))
