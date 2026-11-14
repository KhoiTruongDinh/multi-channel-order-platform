"""Pinned local standalone adapter: API-ready scheduler and forwarded shutdown.

Retain upstream initialization/auth/process commands. This is a development
topology, not a production Airflow supervisor. Never change task/retry state.
"""
import json
import os
from pathlib import Path
import secrets
import signal
import threading
import time
from urllib.request import urlopen

API_HEALTH='http://127.0.0.1:8080/api/v2/monitor/health'


def configure_jwt(directory,environment=None):
    """Share one persisted local signing key BEFORE importing Airflow config."""
    environment=os.environ if environment is None else environment
    key='AIRFLOW__API_AUTH__JWT_SECRET'
    if any(environment.get(name) for name in (
            key+'_CMD',key+'_SECRET','AIRFLOW__API_AUTH__JWT_PRIVATE_KEY_PATH',
            'AIRFLOW__API_AUTH__TRUSTED_JWKS_URL')):
        return  # Respect explicitly configured external/asymmetric key management.
    value=environment.get(key,'')
    if not value:
        directory=Path(directory)
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/'execution-jwt.key'
        if path.is_symlink():
            raise ValueError('local signing key must not be a symlink')
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            value=path.read_text(encoding='utf-8').strip()
        else:
            value=secrets.token_urlsafe(64)
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(value+'\n')
    if len(value.encode())<64:
        raise ValueError('Execution API JWT secret must contain at least64bytes; never auto-rotate a retained key')
    environment[key]=value


def api_ready():
    """Do NOT require scheduler health: that would make startup circular."""
    try:
        with urlopen(API_HEALTH,timeout=2) as response:
            value=json.load(response)
        return isinstance(value,dict) and value.get('metadatabase',{}).get('status')=='healthy'
    except (OSError,ValueError,AttributeError):
        return False


def wait_for_api(cancel,timeout=300,ready=api_ready):
    deadline=time.monotonic()+timeout
    while not cancel.is_set():
        if ready():
            return True
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise TimeoutError('Execution API readiness deadline exceeded')
        cancel.wait(min(1,remaining))
    return False


def gated_subcommand(base,cancel,fail):
    class ReadySubCommand(base):
        def run(self):
            try:
                if self.name=='scheduler':
                    print('LOCAL_STARTUP scheduler waiting for Execution API',flush=True)
                    if not wait_for_api(cancel):
                        return
                    print('LOCAL_STARTUP Execution API ready; starting scheduler',flush=True)
                if cancel.is_set():
                    return
                super().run()
                if not cancel.is_set():
                    raise RuntimeError('Airflow component exited unexpectedly')
            except Exception as error:
                # Exception text may contain connection strings. Only log type.
                print('LOCAL_STARTUP component='+self.name+' failure='+type(error).__name__,flush=True)
                fail()

        def stop(self):
            cancel.set()
            super().stop()
    return ReadySubCommand


def main():
    configure_jwt(Path(os.environ.get('AIRFLOW_HOME','/opt/airflow'))/'state')
    import airflow
    from airflow.cli.commands import standalone_command as upstream
    if airflow.__version__!='3.3.2':
        raise RuntimeError('Review the standalone adapter before changing pinned Airflow3.3.2')
    cancel=threading.Event()
    failed=threading.Event()

    def fail():
        failed.set()
        os.kill(os.getpid(),signal.SIGTERM)

    def shutdown(signum,frame):
        cancel.set()
        # Upstream catches KeyboardInterrupt and stops/joins its own children.
        raise KeyboardInterrupt

    upstream.SubCommand=gated_subcommand(upstream.SubCommand,cancel,fail)
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try:
        upstream.StandaloneCommand().run()
    except KeyboardInterrupt:
        # Also handle shutdown during upstream database initialization.
        cancel.set()
    return 1 if failed.is_set() else 0


if __name__=='__main__':
    raise SystemExit(main())
