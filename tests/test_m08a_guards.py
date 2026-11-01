"""Offline negative guards: no Docker or owner/test mutations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_support import m08a as m


class GuardTests(unittest.TestCase):
    def setUp(self):
        identity = '012345abcdef'
        self.marker = dict(format_version=1,id=identity,project='m08a-'+identity,
            root=str(m.root_for(identity)),repository=str(m.ROOT))
        base = dict(services={name: dict(environment={},healthcheck={}) for name in m.SERVICES})
        base['services']['airflow']['environment']['POLLING_DRAIN_MODE'] = 'true'
        for name in ('postgres','report','airflow','ebay-sim','etsy-sim','etsy-receiver'):
            base['services'][name]['ports'] = [dict(target=5432 if name=='postgres' else 8080,protocol='tcp')]
        self.model = m.make_model(base,self.marker)

    def reject(self, change):
        model, marker = copy.deepcopy(self.model), copy.deepcopy(self.marker)
        change(model,marker)
        with self.assertRaises(m.SafetyError):
            m.validate_model(model,marker)

    def test_valid_model(self):
        m.validate_model(self.model,self.marker)

    def local_model(self):
        marker=copy.deepcopy(self.marker)
        marker.update(profile='m08b',backend='s02-pg',local_playback=True)
        return m.make_model(self.model,marker),marker

    def test_local_playback_allows_only_pipeline_clock_identity(self):
        model,marker=self.local_model(); m.validate_model(model,marker)
        model['services']['airflow']['environment']['S02_DB_PASSWORD']='must-not-leak'
        with self.assertRaises(m.SafetyError): m.validate_model(model,marker)

    def test_local_playback_campaign_and_marker_must_match(self):
        model,marker=self.local_model()
        model['services']['airflow']['environment']['S02_CAMPAIGN_ID']='abcdef123456'
        with self.assertRaises(m.SafetyError): m.validate_model(model,marker)
        model,marker=self.local_model(); marker['local_playback']=False
        with self.assertRaises(m.SafetyError): m.validate_model(model,marker)

    def test_local_playback_is_forbidden_in_a_and_non_airflow_services(self):
        self.reject(lambda model,marker: marker.update(local_playback=True))
        model,marker=self.local_model()
        model['services']['report']['environment']['S02_LOCAL_PLAYBACK']='true'
        with self.assertRaises(m.SafetyError): m.validate_model(model,marker)

    def test_later_invocation_preserves_previous_command_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'evidence').mkdir()
            previous = root / 'evidence/000.log'
            previous.write_text('previous acceptance evidence', encoding='utf-8')
            h = object.__new__(m.Harness)
            h.root, h.marker, h.steps = root, self.marker, []
            def fake(*args, **kwargs):
                kwargs['log'].write_text('new command evidence', encoding='utf-8')
                return ''
            with patch.object(h, 'check'), patch.object(m, 'docker', side_effect=fake):
                h.dc(['down'])
                first = h.steps[0]['log']
                h.steps = []  # A subsequent CLI invocation starts at step zero.
                h.dc(['down'])
            self.assertEqual(previous.read_text(), 'previous acceptance evidence')
            self.assertNotEqual(first, h.steps[0]['log'])
            self.assertEqual(len(list((root / 'evidence').glob('*.log'))), 3)

    def test_memory_gate_rejects_undersized_or_busy_vm(self):
        with self.assertRaises(m.SafetyError):
            m.validate_memory(4*1024**3,0)
        with self.assertRaises(m.SafetyError):
            m.validate_memory(6*1024**3,4*1024**3)
        m.validate_memory(6*1024**3,2*1024**3)
        m.validate_memory(4*1024**3,512*1024**2,dual_airflow=False)

    def test_invalid_ids_and_paths(self):
        for identity in ('', '../owner','ABCDEF012345','multi-channel-order-platform','a'*13):
            with self.subTest(identity=identity),self.assertRaises(m.SafetyError):
                m.root_for(identity)
        self.reject(lambda model,mark:mark.update(root=str(m.ROOT / 'runtime')))
        self.reject(lambda model,mark:mark.update(repository=str(m.ROOT.parent)))

    def test_foreign_project_volume_network_or_service(self):
        self.reject(lambda model,mark:mark.update(project=m.OWNER))
        self.reject(lambda model,mark:model.update(name=m.OWNER))
        self.reject(lambda model,mark:model['volumes']['postgres_data'].update(name=m.OWNER+'_postgres_data'))
        self.reject(lambda model,mark:model['volumes']['postgres_data'].update(external=True))
        self.reject(lambda model,mark:model['networks']['default'].update(name=m.OWNER+'_default'))
        self.reject(lambda model,mark:model['services'].update(unknown_service={}))

    def test_owner_mount_readwrite_and_socket_rejected(self):
        self.reject(lambda model,mark:model['services']['airflow']['volumes'][0].update(source=str(m.ROOT/'runtime/airflow/logs')))
        self.reject(lambda model,mark:model['services']['postgres']['volumes'][1].update(read_only=False))
        self.reject(lambda model,mark:model['services']['report'].update(volumes=[dict(type='bind',source='/var/run/docker.sock',target='/var/run/docker.sock')]))
        self.reject(lambda model,mark:model['services']['airflow'].update(volumes=[]))

    def test_foreign_endpoints_and_schedules_rejected(self):
        self.reject(lambda model,mark:model['services']['report']['environment'].update(PLATFORM_DB_HOST='host.docker.internal'))
        self.reject(lambda model,mark:model['services']['airflow']['environment'].update(WEBSITE_DB_PORT=5433))
        self.reject(lambda model,mark:model['services']['airflow']['environment'].update(ETSY_ORIGIN='https://external.example'))
        self.reject(lambda model,mark:model['services']['airflow']['environment'].update(POLLING_DRAIN_MODE='false'))

    def test_ports_and_capabilities_rejected(self):
        self.reject(lambda model,mark:model['services']['postgres']['ports'][0].update(host_ip='0.0.0.0'))
        self.reject(lambda model,mark:model['services']['report']['ports'][0].update(published=model['services']['postgres']['ports'][0]['published']))
        for key,value in [('privileged',True),('network_mode','host'),('extra_hosts',['postgres:127.0.0.1']),('mem_limit',0)]:
            self.reject(lambda model,mark:model['services']['report'].update({key:value}))

    def test_missing_marker_before_any_docker(self):
        with patch.object(m,'docker') as docker,patch.object(Path,'is_file',return_value=False):
            with self.assertRaises(m.SafetyError):
                m.load(self.marker['id'])
        docker.assert_not_called()

    def test_hash_mismatch_before_any_docker(self):
        marker=self.marker | dict(model_sha256='wrong',env_sha256='wrong',base_sha256='wrong')
        with patch.object(Path,'is_file',return_value=True),patch.object(Path,'read_text',return_value=json.dumps(marker)),patch.object(m,'digest',return_value='actual'),patch.object(m,'docker') as docker:
            with self.assertRaises(m.SafetyError):
                m.load(marker['id'])
        docker.assert_not_called()

    def test_foreign_labels_before_mutation(self):
        foreign=[dict(Labels={'com.docker.compose.project':m.OWNER})]
        def docker(*args,**kwargs):
            if args[:2]==('volume','ls'):
                return self.marker['project']+'_postgres_data'
            if args[:2]==('volume','inspect'):
                return json.dumps(foreign)
            raise AssertionError('Unexpected operation after foreign volume')
        with patch.object(m,'docker',side_effect=docker),self.assertRaises(m.SafetyError):
            m.check_resources(self.marker,self.model)

    def test_colliding_port_prevents_mutation(self):
        with patch.object(m,'docker',return_value=''),patch.object(m,'port_free',return_value=False),self.assertRaises(m.SafetyError):
            m.check_resources(self.marker,self.model)

    def test_path_escape_and_inherited_env(self):
        with patch.object(Path,'resolve',return_value=m.ROOT),self.assertRaises(m.SafetyError):
            m.exact_path(m.root_for(self.marker['id']),m.root_for(self.marker['id']))
        with patch.dict('os.environ',{'POSTGRES_SUPERUSER_PASSWORD':'DO_NOT_USE','COMPOSE_FILE':'owner.yaml','COMPOSE_PROJECT_NAME':m.OWNER}):
            cleaned=m.environment()
        self.assertNotIn('POSTGRES_SUPERUSER_PASSWORD',cleaned)
        self.assertNotIn('COMPOSE_FILE',cleaned)
        self.assertNotIn('COMPOSE_PROJECT_NAME',cleaned)

    def test_marker_id_and_engine_mismatch(self):
        marker=self.marker | dict(model_sha256='hash',env_sha256='hash',base_sha256='hash',engine_id='old')
        def read(path,*args,**kwargs):
            return json.dumps(marker if path.name=='identity.json' else self.model)
        with patch.object(Path,'is_file',return_value=True),patch.object(Path,'read_text',read),patch.object(m,'digest',return_value='hash'),patch.object(m,'engine_id',return_value='new'):
            with self.assertRaisesRegex(m.SafetyError,'engine changed'):
                m.load(marker['id'])
            marker['id']='fedcba543210'
            with self.assertRaisesRegex(m.SafetyError,'ID/marker mismatch'):
                m.load(self.marker['id'])

    def test_actual_container_and_database_guards(self):
        service=self.model['services']['postgres']
        row=dict(Id='test-container',Config=dict(Labels={m.LABEL:self.marker['id'],
            'com.docker.compose.project':self.marker['project'],'com.docker.compose.service':'postgres'},
            Env=[],Image=service.get('image','postgres:test')),
            HostConfig=dict(Privileged=False,NetworkMode=self.marker['project']+'_default',Memory=service['mem_limit'],
                PortBindings={f"{p['target']}/tcp":[dict(HostIp='127.0.0.1',HostPort=p['published'])] for p in service['ports']}),
            State=dict(Running=False),NetworkSettings=dict(Networks={},Ports={}),Mounts=[])
        service['image']='postgres:test'
        for mount in service['volumes']:
            row['Mounts'].append(dict(Destination=mount['target'],RW=not mount.get('read_only',False),
                Source=mount['source'],Name=self.marker['project']+'_postgres_data' if mount['type']=='volume' else ''))
        def fake(*args,**kwargs):
            if args[:2] in (('volume','ls'),('network','ls')):
                return ''
            if args[0]=='ps':
                return 'test-container'
            if args[0]=='inspect':
                return json.dumps([row])
            if args[0]=='exec':
                return 'foreign-system-id'
            raise AssertionError('Unexpected Docker mutation')
        with patch.object(m,'docker',side_effect=fake),patch.object(m,'port_free',return_value=True):
            m.check_resources(self.marker,self.model)
            row['Config']['Image']='owner-image'
            with self.assertRaisesRegex(m.SafetyError,'image tag'):
                m.check_resources(self.marker,self.model)
            row['Config']['Image']='postgres:test'
            removed=row['Mounts'].pop()
            with self.assertRaisesRegex(m.SafetyError,'Missing actual'):
                m.check_resources(self.marker,self.model)
            row['Mounts'].append(removed)
            row['State']['Running']=True
            self.marker['db_system_id']='expected-system-id'
            with self.assertRaisesRegex(m.SafetyError,'database identity'):
                m.check_resources(self.marker,self.model)


if __name__=='__main__':
    unittest.main(verbosity=2)
