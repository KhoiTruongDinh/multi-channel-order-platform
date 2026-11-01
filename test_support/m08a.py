"""Guarded, bounded M08A host harness. No Docker passthrough or volume deletion."""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'infra/compose.yaml'
OWNER = 'multi-channel-order-platform'
LABEL = 'local.m08a.identity'
SERVICES = {'postgres', 'website-simulator', 'website-collector', 'dbt-transform',
    'platform-publisher', 'ebay-sim', 'm05-checks', 'ebay-collector', 'etsy-sim',
    'etsy-receiver', 'scheduler-observer', 'report', 'airflow'}
CAPS = {s: 128 for s in SERVICES} | {'postgres': 384, 'airflow': 1536,
    'dbt-transform': 512, 'platform-publisher': 512, 'm05-checks': 512, 'report': 384}
WRITABLE = {'dbt-transform': {'/app/transformations/target': 'dbt'},
    'airflow': {'/opt/airflow/logs': 'airflow-logs', '/opt/airflow/state': 'airflow-state',
                '/opt/project/transformations/target': 'dbt'}}
READONLY = {'/docker-entrypoint-initdb.d': ROOT / 'infra/postgres/bootstrap',
            '/migrations': ROOT / 'migrations'}
TEST_READS = {'/repo': ROOT, '/fixtures/s01': ROOT / 'fixtures/s01'}
B_TEST_READS = {'/repo/'+name: ROOT/name for name in
    ('tests','ingestion','simulator','orchestration','transformation','fixtures/s01')}


class SafetyError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def root_for(identity):
    require(bool(re.fullmatch('[0-9a-f]{12}', identity)), 'Invalid test ID')
    return ROOT / 'runtime/isolated' / ('m08a-' + identity)


def exact_path(path, expected):
    """Reject traversal, symlinks and junctions, including existing ancestors."""
    path, expected = Path(path), Path(expected)
    require(path.is_absolute() and path == expected, 'Unexpected absolute path')
    require(path.resolve() == path.absolute(), 'Symlink/junction/path escape')
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink() and not getattr(ancestor, 'is_junction', lambda: False)(),
                'Symlink/junction ancestor')


def environment():
    keys = {line.split('=', 1)[0] for line in (ROOT / '.env.example').read_text().splitlines()
            if '=' in line and not line.startswith('#')}
    return {k: v for k, v in os.environ.items() if k not in keys and not k.startswith('COMPOSE_')}


def execute(args, *, payload=None, timeout=30, log=None):
    """Capture private config/inspect output in memory; never echo secrets."""
    try:
        result = subprocess.run(args, input=payload, text=True, encoding='utf-8',
            errors='replace', capture_output=True, timeout=timeout, env=environment(), cwd=ROOT)
    except subprocess.TimeoutExpired as error:
        if log:
            def decoded(value):
                return value.decode('utf-8', 'replace') if isinstance(value, bytes) else value or ''
            log.write_text(f'Command timeout after {timeout}s\n' + decoded(error.stdout) + '\n' + decoded(error.stderr), encoding='utf-8')
        raise SafetyError('Command timeout; inspect retained test state before retry') from None
    if log:
        log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    require(result.returncode == 0, 'Command failed; inspect its ignored evidence log')
    return result.stdout.strip()


def docker(*args, **kwargs):
    return execute(['docker', *args], **kwargs)


def engine_id():
    return docker('info', '--format', '{{.ID}}')


def validate_memory(total, occupied, dual_airflow=True):
    minimum = 6 * 1024**3 if dual_airflow else 3.5 * 1024**3
    require(total >= minimum, 'Insufficient Docker memory for the selected owner/test Airflow topology')
    require(total - occupied >= 3 * 1024**3, 'Full acceptance requires at least 3GiB container-memory headroom')


def resource_preflight(marker, scheduled=True):
    """Fail before writes instead of overloading an already running owner VM."""
    total = int(docker('info', '--format', '{{.MemTotal}}'))
    usage = docker('stats', '--no-stream', '--format', '{{.MemUsage}}')
    occupied = 0
    units = {'B': 1, 'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3,
             'kB': 1000, 'MB': 1000**2, 'GB': 1000**3}
    for line in usage.splitlines():
        match = re.fullmatch(r'([0-9.]+)([A-Za-z]+)', line.split('/')[0].strip())
        require(match and match[2] in units, 'Unknown Docker memory sample')
        occupied += float(match[1]) * units[match[2]]
    owner_airflow = docker('ps','-q','--filter','label=com.docker.compose.project='+OWNER,
        '--filter','label=com.docker.compose.service=airflow')
    if scheduled:
        validate_memory(total, occupied, dual_airflow=bool(owner_airflow))
    else:
        require(total>=3.5*1024**3 and total-occupied>=1.5*1024**3,
            'CLI-only temporal baseline requires >=3.5GiB Docker total and >=1.5GiB headroom')
    ids = docker('ps', '--format', '{{.Label "local.m08a.identity"}}').splitlines()
    require(not any(identity and identity != marker['id'] for identity in ids), 'Another M08A environment is still running')


def port_free(port):
    try:
        with socket.socket() as listener:
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(('127.0.0.1', int(port)))
        return True
    except OSError:
        return False


def new_port(used):
    while True:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        if port not in used:
            used.add(port)
            return port


def compose_args(marker):
    return ['compose', '--project-name', marker['project'], '--project-directory', str(ROOT / 'infra'),
        '--env-file', str(Path(marker['root']) / 'test.env'), '--file',
        str(Path(marker['root']) / 'compose.json'), '--profile', '*']


def make_model(base, marker):
    model = copy.deepcopy(base)
    identity, project, run_root = marker['id'], marker['project'], Path(marker['root'])
    require(set(model['services']) == SERVICES, 'Base service set changed; review isolation policy')
    model['name'] = project
    model['volumes'] = {'postgres_data': {'name': project + '_postgres_data', 'labels': {LABEL: identity}}}
    model['networks'] = {'default': {'name': project + '_default', 'labels': {LABEL: identity}}}
    used = set()
    for name, service in model['services'].items():
        service['labels'] = {LABEL: identity}
        service['networks'] = {'default': None}
        service['mem_limit'] = CAPS[name] * 1024**2
        if name == 'airflow':
            # Avoid repeatedly importing a full Airflow CLI during cold startup.
            # HTTP 200 alone is insufficient: validate the real component status.
            health = "import json,urllib.request; h=json.load(urllib.request.urlopen('http://localhost:8080/api/v2/monitor/health',timeout=5)); assert all(h[k]['status']=='healthy' for k in ('metadatabase','scheduler','dag_processor'))"
            service['healthcheck'].update(test=['CMD','python','-c',health],timeout='10s',interval='15s',start_period='90s')
        if 'build' in service:
            service['image'] = project + '-' + name
        for port in service.get('ports', []):
            port.update(host_ip='127.0.0.1', published=str(new_port(used)))
        mounts = []
        if name == 'postgres':
            mounts = [dict(type='volume', source='postgres_data', target='/var/lib/postgresql/data'),
                *[dict(type='bind', source=str(source), target=target, read_only=True)
                  for target, source in READONLY.items()]]
            # The entrypoint's temporary bootstrap server accepts Unix sockets
            # before initialization completes; require the final TCP listener.
            service['healthcheck']['test'] = ['CMD', 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', '-d', 'postgres']
        for target, relative in WRITABLE.get(name, {}).items():
            mounts.append(dict(type='bind', source=str(run_root / 'binds' / relative), target=target))
        if mounts:
            service['volumes'] = mounts
        else:
            require(not service.get('volumes'), 'Unexpected base writable mount')
    if marker.get('profile') == 'm08b':
        control_token = secrets.token_urlsafe(32)
        for name in ('ebay-sim','etsy-sim'):
            model['services'][name]['environment'].update(SIMULATOR_MODE='s02',
                S02_CONTROL_TOKEN=control_token)
        if marker.get('backend') == 's02-pg':
            for name in ('ebay-sim','etsy-sim'):
                env = model['services'][name]['environment']
                env.pop('S02_CONTROL_TOKEN')
                env.update(SIMULATOR_MODE='s02-pg',S02_CAMPAIGN_ID=identity,
                    S02_DB_HOST='postgres',S02_DB_PASSWORD=secrets.token_urlsafe(32))
        env = model['services']['airflow']['environment']
        if marker.get('backend') == 's02-pg':
            env['POLLING_MAPPING_VERSION'] = 's02-catalog-v1'
        if marker.get('local_playback',False):
            env.update(S02_LOCAL_PLAYBACK='true',S02_CAMPAIGN_ID=identity)
        env['POLLING_DRAIN_MODE'] = 'false'
        if marker.get('drain_signal',False):
            env['POLLING_DRAIN_FILE'] = '/opt/airflow/state/polling-drain'
        env['POLLING_SLOT_WAIT_SECONDS'] = str(marker.get('slot_wait_seconds',15))
        for key in ('WEBSITE_POLL_INTERVAL_SECONDS','EBAY_POLL_INTERVAL_SECONDS',
                    'ETSY_INBOX_INTERVAL_SECONDS','ETSY_RECOVERY_INTERVAL_SECONDS'):
            env[key] = str(marker.get('interval_seconds',30))
        from datetime import timedelta
        initial = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        for key in ('WEBSITE_POLL_INITIAL_START','EBAY_POLL_INITIAL_START','ETSY_RECOVERY_INITIAL_START'):
            env[key] = initial
    return model


def validate_model(model, marker):
    identity, project = marker['id'], marker['project']
    run_root = root_for(identity)
    require(marker['format_version'] == 1 and project == 'm08a-' + identity, 'Marker/project mismatch')
    exact_path(marker['root'], run_root)
    require(marker['repository'] == str(ROOT), 'Wrong repository marker')
    require(model['name'] == project and set(model['services']) == SERVICES, 'Wrong project/services')
    require(model.get('volumes') == {'postgres_data': {'name': project + '_postgres_data', 'labels': {LABEL: identity}}},
            'Foreign/external volume')
    require(model.get('networks') == {'default': {'name': project + '_default', 'labels': {LABEL: identity}}},
            'Foreign/external network')
    require(not (set(model) - {'name', 'services', 'volumes', 'networks'}), 'Unexpected model capability')
    all_ports = set()
    for name, service in model['services'].items():
        require(service.get('labels') == {LABEL: identity} and service.get('networks') == {'default': None}, 'Service identity/network')
        for key in ('privileged', 'network_mode', 'pid', 'ipc', 'devices', 'cap_add', 'external_links',
                    'links', 'volumes_from', 'container_name', 'env_file', 'secrets', 'configs', 'extends', 'extra_hosts'):
            require(not service.get(key), 'Unsupported service capability: ' + key)
        require(service.get('mem_limit') == CAPS[name] * 1024**2, 'Resource cap mismatch')
        env = service.get('environment', {})
        for key in ('PLATFORM_DB_HOST', 'WEBSITE_DB_HOST','S02_DB_HOST'):
            require(env.get(key, 'postgres') == 'postgres', 'Foreign DB endpoint')
        for key in ('PLATFORM_DB_PORT', 'WEBSITE_DB_PORT'):
            require(str(env.get(key, 5432)) == '5432', 'Foreign DB port')
        for key, expected in [('EBAY_ORIGIN', 'http://ebay-sim'), ('ETSY_ORIGIN', 'http://etsy-sim')]:
            require(env.get(key, expected) == expected, 'Foreign marketplace endpoint')
        require('build' not in service or service.get('image') == project + '-' + name, 'Shared image tag')
        for port in service.get('ports', []):
            value = int(port['published'])
            require(port['host_ip'] == '127.0.0.1' and port.get('protocol', 'tcp') == 'tcp'
                    and 1024 <= value <= 65535 and value not in all_ports, 'Unsafe/duplicate host port')
            all_ports.add(value)
        expected = {target: (str(run_root / 'binds' / relative), False)
                    for target, relative in WRITABLE.get(name, {}).items()}
        if name == 'postgres':
            expected |= {target: (str(source), True) for target, source in READONLY.items()}
            expected['/var/lib/postgresql/data'] = ('postgres_data', False)
        seen = set()
        for mount in service.get('volumes', []):
            target = mount['target']
            require(target not in seen and target in expected, 'Unexpected/duplicate mount target')
            seen.add(target)
            source, readonly = expected[target]
            require(mount['source'] == source and bool(mount.get('read_only')) == readonly, 'Wrong mount source/mode')
            require(mount['type'] == ('volume' if source == 'postgres_data' else 'bind'), 'Wrong mount type')
            if mount['type'] == 'bind':
                exact_path(source, Path(source))
        require(seen == set(expected), 'Missing isolation mount')
    profile = marker.get('profile','m08a')
    require(profile in ('m08a','m08b'), 'Unknown test profile')
    require(type(marker.get('local_playback',False)) is bool,'Invalid local playback identity')
    require(not marker.get('local_playback',False) or (profile=='m08b' and marker.get('backend')=='s02-pg'),
            'Local playback requires temporal B')
    require(profile=='m08b' or marker.get('backend','ram')=='ram','Temporal backend forbidden outside B')
    env = model['services']['airflow']['environment']
    require(env['POLLING_DRAIN_MODE'] == ('false' if profile=='m08b' else 'true'), 'Test schedules not drained/profile mismatch')
    if profile == 'm08a':
        require(not any(k in service.get('environment',{}) for service in model['services'].values()
                        for k in ('SIMULATOR_MODE','S02_CONTROL_TOKEN','POLLING_DRAIN_FILE','S02_DB_PASSWORD','S02_CAMPAIGN_ID','S02_LOCAL_PLAYBACK')), 'S02 controls forbidden in A profile')
    if profile == 'm08b':
        require(env.get('S02_LOCAL_PLAYBACK')==('true' if marker.get('local_playback',False) else None),
                'Local logical clock/profile mismatch')
        require(env.get('S02_CAMPAIGN_ID')==(identity if marker.get('local_playback',False) else None),
                'Local pipeline campaign identity mismatch')
        require(type(marker.get('drain_signal',False)) is bool, 'Invalid B drain capability')
        require(env.get('POLLING_DRAIN_FILE')==('/opt/airflow/state/polling-drain' if marker.get('drain_signal',False) else None),
                'B drain signal mismatch')
        require(type(marker.get('interval_seconds',30)) is int and marker.get('interval_seconds',30) in (30,180),
                'Unsupported B interval identity')
        require(type(marker.get('slot_wait_seconds',15)) is int and marker.get('slot_wait_seconds',15) in (15,300),
                'Unsupported B coordinator wait identity')
        require(env.get('POLLING_SLOT_WAIT_SECONDS')==str(marker.get('slot_wait_seconds',15)), 'B coordinator wait mismatch')
        require(marker.get('backend','ram') in ('ram','s02-pg'), 'Unknown source backend')
        if marker.get('backend') == 's02-pg':
            require(env.get('POLLING_MAPPING_VERSION') == 's02-catalog-v1', 'Temporal mapping mismatch')
            for name in ('ebay-sim','etsy-sim'):
                source_env=model['services'][name]['environment']
                require(source_env.get('SIMULATOR_MODE')=='s02-pg' and source_env.get('S02_CAMPAIGN_ID')==identity
                    and source_env.get('S02_DB_HOST')=='postgres' and 'S02_CONTROL_TOKEN' not in source_env
                    and bool(re.fullmatch('[a-zA-Z0-9_-]{32,}',source_env.get('S02_DB_PASSWORD',''))), 'Temporal reader config mismatch')
        else:
            control_token = model['services']['ebay-sim']['environment'].get('S02_CONTROL_TOKEN','')
            require(bool(re.fullmatch('[a-zA-Z0-9_-]{32,}', control_token)), 'Missing B control identity')
            for name in ('ebay-sim','etsy-sim'):
                expected = {'SIMULATOR_MODE':'s02','S02_CONTROL_TOKEN':control_token}
                require(all(model['services'][name]['environment'].get(k)==v for k,v in expected.items()), 'B source control mismatch')
        for name, service in model['services'].items():
            if name not in ('ebay-sim','etsy-sim'):
                forbidden=('S02_CONTROL_TOKEN','SIMULATOR_MODE','S02_DB_PASSWORD')
                if name!='airflow' or not marker.get('local_playback',False): forbidden+=('S02_CAMPAIGN_ID',)
                if name!='airflow': forbidden+=('S02_LOCAL_PLAYBACK',)
                require(not any(k in service.get('environment',{}) for k in forbidden), 'Test controls leaked to pipeline')
        for key in ('WEBSITE_POLL_INTERVAL_SECONDS','EBAY_POLL_INTERVAL_SECONDS',
                    'ETSY_INBOX_INTERVAL_SECONDS','ETSY_RECOVERY_INTERVAL_SECONDS'):
            require(env.get(key)==str(marker.get('interval_seconds',30)), 'B polling interval mismatch')


def init(profile='m08a', backend='ram', local_playback=False):
    require(profile in ('m08a','m08b'), 'Unknown test profile')
    require(backend in ('ram','s02-pg') and (profile=='m08b' or backend=='ram'), 'Invalid backend/profile')
    require(type(local_playback) is bool and (not local_playback or (profile=='m08b' and backend=='s02-pg')),
            'Local playback requires temporal B')
    identity = uuid.uuid4().hex[:12]
    run_root = root_for(identity)
    exact_path(run_root, run_root)
    run_root.mkdir(parents=True, exist_ok=False)
    values = {}
    for line in (ROOT / '.env.example').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            values[key] = value
    for key in values:
        if 'PASSWORD' in key or key.endswith('_TOKEN'):
            values[key] = secrets.token_urlsafe(24)
    values.update(POSTGRES_SUPERUSER='postgres', POLLING_DRAIN_MODE='true',
        ETSY_SIGNING_SECRET='whsec_' + base64.b64encode(secrets.token_bytes(32)).decode())
    env_file = run_root / 'test.env'
    with env_file.open('x', encoding='utf-8') as handle:
        handle.write(''.join(f'{k}={v}\n' for k, v in values.items()))
    env_file.chmod(0o600)
    marker = dict(format_version=1, id=identity, project='m08a-' + identity,
        repository=str(ROOT), root=str(run_root), engine_id=engine_id(), created_at=utc(), db_system_id=None)
    if profile == 'm08b':
        marker.update(profile=profile, interval_seconds=180, slot_wait_seconds=300, drain_signal=True)
        if backend=='s02-pg':
            marker['backend']=backend
        if local_playback: marker['local_playback']=True
    base = json.loads(docker('compose', '--project-name', marker['project'], '--env-file', str(env_file),
        '--file', str(BASE), '--profile', '*', 'config', '--format', 'json'))
    model = make_model(base, marker)
    validate_model(model, marker)
    for name in ('dbt', 'airflow-logs', 'airflow-state'):
        (run_root / 'binds' / name).mkdir(parents=True)
    (run_root / 'evidence').mkdir()
    config = run_root / 'compose.json'
    with config.open('x', encoding='utf-8') as handle:
        json.dump(model, handle, indent=2)
    config.chmod(0o600)
    marker.update(model_sha256=digest(config), env_sha256=digest(env_file), base_sha256=digest(BASE))
    save_marker(marker, exclusive=True)
    print(f'{profile.upper()} initialized id={identity}; private configuration under {run_root.relative_to(ROOT)}')
    return identity


def save_marker(marker, exclusive=False):
    path = Path(marker['root']) / 'identity.json'
    with path.open('x' if exclusive else 'w', encoding='utf-8') as handle:
        json.dump(marker, handle, indent=2)


def load(identity):
    run_root = root_for(identity)
    exact_path(run_root, run_root)
    for name in ('identity.json', 'compose.json', 'test.env'):
        exact_path(run_root / name, run_root / name)
        require((run_root / name).is_file(), 'Missing test marker/config')
    marker = json.loads((run_root / 'identity.json').read_text())
    require(marker['id'] == identity, 'Requested ID/marker mismatch')
    require(marker['model_sha256'] == digest(run_root / 'compose.json') and
        marker['env_sha256'] == digest(run_root / 'test.env') and marker['base_sha256'] == digest(BASE), 'Config/env/base hash mismatch')
    model = json.loads((run_root / 'compose.json').read_text())
    validate_model(model, marker)
    require(marker['engine_id'] == engine_id(), 'Docker engine changed')
    return marker, model


def owned(labels, marker):
    return labels.get('com.docker.compose.project') == marker['project'] and labels.get(LABEL) == marker['id']


def check_resources(marker, model):
    """Inspect actual daemon resources as well as file/config intentions."""
    for kind, resource in [('volume', marker['project'] + '_postgres_data'),
                           ('network', marker['project'] + '_default')]:
        listed = docker(kind, 'ls', '--format', '{{.Name}}').splitlines()
        if resource in listed:
            row = json.loads(docker(kind, 'inspect', resource))[0]
            require(owned(row.get('Labels') or {}, marker), 'Foreign resource labels')
    ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + marker['project']).split()
    occupied = set()
    if ids:
        for row in json.loads(docker('inspect', *ids)):
            labels = row['Config']['Labels'] or {}
            name = labels.get('com.docker.compose.service')
            require(owned(labels, marker) and name in SERVICES, 'Foreign container/service labels')
            service = model['services'][name]
            require(not row['HostConfig']['Privileged'], 'Unsafe container')
            require(row['Config']['Image'] == service['image'], 'Actual foreign image tag')
            require(row['HostConfig']['NetworkMode'] == marker['project'] + '_default', 'Actual network mode mismatch')
            require(row['HostConfig']['Memory'] == service['mem_limit'], 'Actual container resource cap')
            networks = row['NetworkSettings']['Networks']
            require(set(networks) <= {marker['project'] + '_default'}, 'Actual foreign network')
            expected = {v['target']: v for v in service.get('volumes', [])}
            require(set(expected) <= {mount['Destination'] for mount in row['Mounts']}, 'Missing actual isolation mount')
            for mount in row['Mounts']:
                target = mount['Destination']
                if target not in expected:
                    reads = B_TEST_READS if marker.get('profile')=='m08b' else TEST_READS
                    require(labels.get('com.docker.compose.oneoff', '').lower() == 'true' and
                        target in reads and not mount['RW'], 'Unexpected actual mount')
                    source = str(reads[target])
                else:
                    spec = expected[target]
                    require(mount['RW'] != bool(spec.get('read_only')), 'Actual mount mode')
                    if spec['type'] == 'volume':
                        require(mount.get('Name') == marker['project'] + '_postgres_data', 'Actual foreign volume')
                        continue
                    source = spec['source']
                # Docker Desktop translates host paths; its original-source labels
                # are checked rather than trusting a broad /run/desktop prefix.
                desktop = next((v for k, v in labels.items() if k.startswith('desktop.docker.io/binds/') and k.endswith('/Source')
                    and labels.get(k[:-6] + 'Target') == target), None)
                require((desktop or mount['Source']) == source, 'Actual foreign bind source')
            for key, value in service.get('environment', {}).items():
                require(f'{key}={value}' in row['Config']['Env'], 'Actual environment mismatch')
            for bindings in (row['NetworkSettings'].get('Ports') or {}).values():
                for binding in bindings or []:
                    require(binding['HostIp'] == '127.0.0.1', 'Actual public host port')
                    occupied.add(int(binding['HostPort']))
            expected_ports = {f"{p['target']}/{p.get('protocol','tcp')}":
                [{'HostIp': '127.0.0.1', 'HostPort': str(p['published'])}] for p in service.get('ports', [])}
            if labels.get('com.docker.compose.oneoff', '').lower() == 'true':
                expected_ports = {}
            require((row['HostConfig'].get('PortBindings') or {}) == expected_ports, 'Actual port binding mismatch')
            if name == 'postgres' and row['State']['Running'] and marker.get('db_system_id'):
                deadline = time.monotonic() + 30
                while True:
                    try:
                        actual = docker('exec', row['Id'], 'psql', '-XAt', '-U', 'postgres', '-d', 'postgres',
                            '-c', 'SELECT system_identifier FROM pg_control_system();')
                        break
                    except SafetyError:
                        require(time.monotonic() < deadline, 'Test database not ready for identity guard')
                        time.sleep(1)
                require(actual == marker['db_system_id'], 'Actual foreign database identity')
    for service in model['services'].values():
        for port in service.get('ports', []):
            number = int(port['published'])
            require(number in occupied or port_free(number), 'Host port already in use')


class Harness:
    def __init__(self, identity):
        self.marker, self.model = load(identity)
        self.root = Path(self.marker['root'])
        self.steps = []

    def check(self):
        marker, model = load(self.marker['id'])
        check_resources(marker, model)
        # Also ensure Docker accepts the generated configuration, without printing it.
        docker(*compose_args(marker), 'config', '--quiet')

    def dc(self, args, payload=None, timeout=180):
        self.check()
        # A later check/stop invocation has a new step counter: never overwrite
        # evidence from an earlier acceptance under the same retained run ID.
        log = self.root / 'evidence' / f'{len(self.steps):03d}-{uuid.uuid4().hex}.log'
        log.touch(exist_ok=False)
        step = dict(command=args, started_at=utc(), status='RUNNING', log=log.name)
        self.steps.append(step)
        try:
            result = docker(*compose_args(self.marker), *args, payload=payload, timeout=timeout, log=log)
            step['status'] = 'PASS'
            return result
        except SafetyError:
            step['status'] = 'FAIL'
            raise
        finally:
            step['finished_at'] = utc()
            print(f"{self.marker.get('profile','m08a').upper()} step={len(self.steps)} {args[0]} {step['status']}", flush=True)

    def sql(self, query, db='data_platform'):
        return self.dc(['exec', '-T', 'postgres', 'psql', '-X', '--set', 'ON_ERROR_STOP=1',
            '--username', 'postgres', '--dbname', db, '--tuples-only', '--no-align'], payload=query)

    def migration_rerun(self):
        self.dc(['exec', '-T', 'postgres', 'bash', '/docker-entrypoint-initdb.d/00-bootstrap.sh'])

    def test_db(self, first=False):
        value = self.sql('SELECT system_identifier FROM pg_control_system();', 'postgres')
        require(bool(re.fullmatch('[0-9]+', value)), 'Invalid test database identity')
        if first:
            require(self.marker['db_system_id'] is None, 'Test DB identity already bound')
            self.marker['db_system_id'] = value
            save_marker(self.marker)
        require(value == self.marker['db_system_id'], 'Foreign database system identifier')
        return value

    def run(self, service, *command, reads=False, entrypoint=None, timeout=180):
        require(service in SERVICES, 'Non-allowlisted service')
        args = ['run', '--rm', '-T', '--no-deps']
        if reads:
            mounts = B_TEST_READS if self.marker.get('profile')=='m08b' else TEST_READS
            for target, source in mounts.items():
                args += ['--volume', f'{source}:{target}:ro']
        if entrypoint:
            args += ['--entrypoint', entrypoint]
        return self.dc(args + [service, *command], timeout=timeout)


def owner_container():
    ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + OWNER,
        '--filter', 'label=com.docker.compose.service=postgres').split()
    require(len(ids) == 1, 'Owner PostgreSQL must be running for protected-signature acceptance')
    return ids[0]


def owner_sql(container, query, db='data_platform'):
    return docker('exec', '-i', container, 'psql', '-X', '--set', 'ON_ERROR_STOP=1', '--username',
        'postgres', '--dbname', db, '--tuples-only', '--no-align', payload=query)


def owner_idle(container):
    require(owner_sql(container, "SELECT count(*) FROM dag_run WHERE state IN ('queued','running');", 'airflow_meta') == '0', 'Owner DAG active; need quiet window')
    require(owner_sql(container, "SELECT count(*) FROM dag WHERE NOT is_paused AND dag_id<>'website_orders';", 'airflow_meta') == '0', 'Owner periodic/replay DAG enabled; need quiet window')
    require(owner_sql(container, "SELECT count(*) FROM ops.transform_batches WHERE status IN ('FROZEN','BUILDING','TESTED');") == '0', 'Owner batch active')
    if owner_sql(container,"SELECT to_regclass('s02.live_batches') IS NOT NULL;",'marketplace_sim')=='t':
        workers=docker('ps','-q','--filter','label=com.docker.compose.project='+OWNER,
                       '--filter','label=com.docker.compose.service=live-source').split()
        if workers:
            pending=owner_sql(container,'''SELECT
              (SELECT count(*) FROM s02.website_versions v JOIN s02.live_batches b USING(campaign_id)
               LEFT JOIN s02.live_website_progress p USING(campaign_id,order_id)
               WHERE v.sequence>coalesce(p.sequence,0))+
              (SELECT count(*) FROM s02.deliveries d JOIN s02.live_batches b USING(campaign_id)
               WHERE NOT d.omitted AND d.delivered_at IS NULL);''','marketplace_sim')
            require(pending=='0','Owner live source has pending emissions; need an approved producer quiet window, not only Airflow stop')


def signature_query(tables):
    parts = [f"SELECT '{t}' AS relation,count(*) AS rows,md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) AS hash FROM {t} t" for t in tables]
    return 'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout=10000;\n' + '\nUNION ALL\n'.join(parts) + '; COMMIT;'


PROTECTED = ['raw.raw_records', 'core.orders_current', 'core.order_lines_current', 'core.order_snapshot_history',
    'core.order_line_snapshot_history', 'core.snapshot_evidence', 'ops.pipeline_runs', 'ops.task_attempts',
    'ops.processing_work', 'ops.webhook_inbox', 'ops.webhook_delivery_attempts', 'ops.extraction_checkpoints',
    'ops.publication_state', 'config.product_mapping', 'ops.transform_batches', 'ops.batch_inputs',
    'ops.data_exceptions', 'ops.polling_cycles', 'ops.etsy_work_context', 'ops.etsy_http_attempts',
    'ops.execution_measurements', 'mart.order_activity_daily', 'mart.product_activity_daily',
    'mart.order_status_current', 'mart.source_health']


def protected_signature(container):
    value = owner_sql(container, signature_query(PROTECTED))
    source = owner_sql(container, signature_query(['public.' + t for t in
        ('customers','products','product_variants','orders','order_items','payment_transactions','shipments','shipment_items','cancellation_requests')]), 'website_source')
    marketplace=''
    if owner_sql(container,"SELECT to_regclass('s02.live_batches') IS NOT NULL;",'marketplace_sim')=='t':
        marketplace=owner_sql(container,signature_query(['s02.'+t for t in
            ('campaigns','local_datasets','orders','components','versions','website_versions',
             'deliveries','playback','live_batches','live_website_progress')]),'marketplace_sim')
    return hashlib.sha256((value + source + marketplace).encode()).hexdigest()


def baseline(h):
    from test_support.m08a_baseline import seed_and_check
    seed_and_check(h)


def owner_absent():
    for args in [('ps','-aq'), ('volume','ls','-q'), ('network','ls','-q')]:
        require(not docker(*args,'--filter','label=com.docker.compose.project='+OWNER),
                'CI mode requires owner project completely absent')
    for args in [('ps','-a','--format','{{.Names}}'),('volume','ls','--format','{{.Name}}'),
                 ('network','ls','--format','{{.Name}}')]:
        require(not any(name==OWNER or name.startswith((OWNER+'-',OWNER+'_'))
                        for name in docker(*args).splitlines()), 'CI mode found owner-named resource')


def accept(h, baseline_fn=None, ci=False, scheduled=True):
    require(h.marker.get('profile','m08a') == ('m08b' if baseline_fn else 'm08a'),
            'Use the matching profile acceptance entrypoint')
    report = dict(format_version=1, id=h.marker['id'], project=h.marker['project'],
        code_sha=execute(['git', 'rev-parse', 'HEAD']),
        dirty_worktree=bool(execute(['git', 'status', '--porcelain'])),
        harness_hashes={name: digest(ROOT / 'test_support' / name) for name in ('m08a.py','m08a_baseline.py')},
        protected_tables=list(PROTECTED), started_at=utc(), status='FAIL', teardown='NOT_RUN')
    h.report = report
    if baseline_fn:
        report['harness_hashes'].update({name: digest(ROOT/name) for name in (
            'test_support/m08b.py','test_support/s02_inputs.py','simulator/s02_store.py',
            'simulator/website_s02.py','simulator/ebay_api.py','simulator/etsy_api.py',
            'orchestration/scheduling.py','orchestration/dags/polling_orders.py','orchestration/dags/etsy_orders.py')})
        if h.marker.get('backend')=='s02-pg':
            report['harness_hashes'].update({name:digest(ROOT/name) for name in (
                'test_support/m08b_temporal.py','test_support/s02_plan.py','test_support/s02_diverse.py',
                'tools/s02_data/references.py',
                'test_support/s02_oracle.py','simulator/s02_temporal.py',
                'migrations/marketplace_sim/001_s02_temporal.sql','fixtures/s02/catalog.json')})
    report['protection_mode'] = 'owner_absent_ci' if ci else 'owner_signature'
    if ci:
        owner_absent()
        owner = None
        report['protected_before'] = 'OWNER_ABSENT'
    else:
        owner = owner_container()
        owner_idle(owner)
        report['protected_before'] = protected_signature(owner)
    # Fresh test only; never rewind a reused source DB or adopt existing volume.
    h.check()
    require(scheduled or (h.marker.get('backend')=='s02-pg' and baseline_fn is not None),
            'CLI topology only allowed for temporal baseline')
    resource_preflight(h.marker,scheduled=scheduled)
    require(h.marker['project'] + '_postgres_data' not in docker('volume', 'ls', '--format', '{{.Name}}').splitlines(), 'Acceptance requires a fresh test volume/new ID')
    # Exclusive latch prevents two concurrent accept invocations from both passing
    # the volume-absence check. Retain it as audit; never reuse/reseed this run ID.
    with (h.root / 'evidence/accept.started').open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(dict(started_at=utc(),pid=os.getpid())))
    try:
        h.dc(['build', *sorted(SERVICES - {'postgres','m05-checks'})], timeout=600)
        if baseline_fn:
            names=sorted(SERVICES-{'m05-checks'})
            ids=docker('image','inspect','--format','{{.Id}}',*[h.model['services'][name]['image'] for name in names]).splitlines()
            require(len(ids)==len(names),'Image identity capture failed')
            report['images']=dict(zip(names,ids))
        h.dc(['up', '--detach', '--wait', '--wait-timeout', '180', 'postgres'])
        report['test_db_system_id'] = h.test_db(first=True)
        if owner:
            require(report['test_db_system_id'] != owner_sql(owner, 'SELECT system_identifier FROM pg_control_system();', 'postgres'), 'Test shares owner DB')
        h.migration_rerun()
        (baseline_fn or baseline)(h)
        report['status'] = 'PASS'
    except Exception as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        cleanup_error = None
        protected_error = None
        try:
            h.dc(['down', '--remove-orphans', '--timeout', '30'])
            report['teardown'] = 'PASS'
        except Exception as error:
            report.update(status='FAIL', teardown='FAIL', cleanup_failure=str(error))
            cleanup_error = error
        try:
            if ci:
                owner_absent()
                report['protected_after'] = 'OWNER_ABSENT'
            else:
                owner_idle(owner)
                report['protected_after'] = protected_signature(owner)
            require(report['protected_before'] == report['protected_after'], 'Protected owner state changed/inconclusive')
            report['protected_check'] = 'PASS'
        except Exception as error:
            report.update(status='INCONCLUSIVE' if report['status']=='PASS' else 'FAIL',
                protected_check='INCONCLUSIVE', protected_failure=str(error))
            protected_error = error
        finally:
            report.update(finished_at=utc(), steps=h.steps)
            (h.root / 'evidence/result.json').write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
            (h.root / 'evidence/accept.finished').write_text(report['finished_at'], encoding='utf-8')
        if cleanup_error or protected_error:
            raise cleanup_error or protected_error
    protection = 'owner absence verified' if ci else 'owner signature unchanged'
    print(f"{h.marker.get('profile','m08a').upper()} acceptance PASS id={h.marker['id']}; isolated volume/evidence retained, {protection}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init','check','accept','stop'))
    parser.add_argument('--id')
    args = parser.parse_args()
    if args.action == 'init':
        require(args.id is None, 'Init allocates its own ID')
        init()
    else:
        require(args.id is not None, 'Explicit test ID required')
        h = Harness(args.id)
        if args.action == 'accept':
            accept(h)
        elif args.action == 'stop':
            require(not (h.root / 'evidence/accept.started').exists() or
                (h.root / 'evidence/accept.finished').exists(), 'Acceptance active/interrupted; inspect before explicit recovery')
            h.dc(['down','--remove-orphans','--timeout','30'])
        else:
            h.check()
            print('M08A preflight PASS (not runtime acceptance)')


if __name__ == '__main__':
    try:
        main()
    except SafetyError as error:
        print(f'M08A refused/failed: {error}. No automatic reset.', file=sys.stderr)
        sys.exit(1)
    except (KeyError, ValueError, OSError):
        # Do not echo Docker/config exceptions containing env or interpolated data.
        print('M08A refused/failed; inspect validated test evidence. No automatic reset.', file=sys.stderr)
        sys.exit(1)
