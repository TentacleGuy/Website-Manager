import json,os,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _temp=tempfile.TemporaryDirectory();os.environ['VMM_DATA']=_temp.name
import system_service as services
import store

class SystemServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        for key in services.AREAS:(self.root/key).mkdir()
        (self.root/'shared').mkdir();(self.root/'shared/compose.json').write_text(json.dumps({'services':{'php84':{},'db':{},'phpmyadmin':{},'arbitrary':{}}}))
        for context in (patch.object(services,'DATA',self.root),patch.object(services,'STATE',self.root/'report.json'),patch.object(services,'redact',side_effect=str)):
            context.start();self.addCleanup(context.stop)
    def row(self,project,service,ident='a'*12,networks=''):
        return {'ID':ident,'State':'running','Status':'Up','Networks':networks,'Labels':'com.docker.compose.project='+project+',com.docker.compose.service='+service}
    def test_only_own_services_and_proven_legacy_gateway_are_controllable(self):
        rows=[self.row('unrelated','db'),self.row('vmm-runtime','php84'),self.row('infra','traefik','b'*12,'vmm-gateway'),self.row('infra','dns','c'*12),self.row('vmm-runtime','arbitrary')]
        with patch.object(services,'docker',return_value='\n'.join(map(json.dumps,rows))):
            self.assertEqual(set(services.containers()),{'runtime:php84','gateway:traefik','gateway:dns'})
        with patch.object(services,'docker',return_value=json.dumps(self.row('infra','dns'))):self.assertEqual(services.containers(),{})
    def test_ambiguous_services_are_not_controlled(self):
        rows=[self.row('vmm-runtime','db'),self.row('vmm-runtime','db','b'*12)]
        with patch.object(services,'docker',return_value='\n'.join(map(json.dumps,rows))):
            with self.assertRaisesRegex(ValueError,'Mehrere Container'):services.containers()
    def test_check_uses_real_write_probe_without_leaving_files(self):
        def docker(*args,**kwargs):
            if args[0]=='ps':return json.dumps(self.row('vmm-runtime','php84'))
            if args[0]=='network':return '[{"Containers":{"one":{}}}]'
            return '28.0'
        with patch.object(services,'docker',side_effect=docker),patch.object(services,'own_container',return_value=None),patch.object(services,'records',return_value=[]):services.check()
        value=services.status();storage=[p for p in value['permissions'] if p['name'].startswith('Speicherzugriff')]
        self.assertEqual(len(storage),6);self.assertTrue(all(p['status']=='ok' for p in storage))
        self.assertFalse(list(self.root.rglob('.vmm-access-*')))
        self.assertFalse(value['desktop_registered']);self.assertEqual(value['permissions'][-1]['status'],'unknown')
    def test_docker_failure_still_reports_storage_permissions(self):
        with patch.object(services,'docker',side_effect=ValueError('socket denied')):services.check()
        value=services.status();self.assertEqual(value['permissions'][0]['status'],'error');self.assertTrue(any(p['name']=='Speicherzugriff · Projekte' and p['status']=='ok' for p in value['permissions']))
    def test_restart_uses_validated_container_id_without_shell(self):
        with patch.object(services,'ensure_idle'),patch.object(services,'containers',return_value={'runtime:php84':{'id':'a'*12}}),patch.object(services,'docker') as docker,patch.object(services,'check'):
            services.transition('runtime:php84','restart')
        docker.assert_called_once_with('restart','--time','20','a'*12,timeout=60)
    def test_unknown_service_or_action_never_starts_a_job(self):
        with patch.object(services,'job') as job:
            for body in ({'service':'unrelated','action':'stop'},{'service':[],'action':'stop'},{'service':'runtime:php84','action':'rm'}):
                with self.assertRaises(ValueError):services.request(body)
        job.assert_not_called()
    def test_service_stop_is_blocked_while_a_project_job_is_active(self):
        conn=sqlite3.connect(self.root/'jobs.sqlite');conn.execute('CREATE TABLE jobs(resource TEXT,status TEXT)');conn.execute("INSERT INTO jobs VALUES('example','running')");conn.commit()
        with patch.object(services,'db',return_value=conn),patch('storage_service.busy',return_value=False),patch('storage_service.ACTIVE_UPLOADS',0):
            with self.assertRaisesRegex(ValueError,'laufende Aufgaben'):services.ensure_idle()
        conn.close()
    def test_new_project_jobs_wait_for_service_controls(self):
        conn=sqlite3.connect(self.root/'jobs.sqlite');conn.execute('CREATE TABLE jobs(resource TEXT,kind TEXT,status TEXT)');conn.execute("INSERT INTO jobs VALUES('system-services','service-control','running')");conn.commit()
        with patch.object(store,'DATA',self.root),patch.object(store,'db',return_value=conn),patch('storage_service.busy',return_value=False),patch.object(store,'POOL') as pool:
            with self.assertRaisesRegex(ValueError,'Dienstaktion'):store.job('example','snapshot',lambda:None)
        pool.submit.assert_not_called();conn.close()

if __name__=='__main__':unittest.main()
