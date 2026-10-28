import sys
from pathlib import Path
import unittest
import json
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from runtime import PHP, compose, ports, slug, host_path, project_links, preview_ports

class RuntimeTests(unittest.TestCase):
    def test_port_contract(self):
        self.assertEqual(ports('7.4'),(8074,8174))
        self.assertEqual(ports('8.0'),(8080,8180))
        self.assertEqual(ports('8.4'),(8084,8184))

    def test_slug_rejects_paths_and_shell(self):
        for name in ('../x','hello.world','foo;id','UPPER','','a'*41,None):
            with self.assertRaises(ValueError):slug(name)

    def test_isolation_routing_and_shared_data(self):
        p={'slug':'demo','php':'8.4','db_password':'test','db_root_password':'root','storage':'files'}
        result=compose(p,'/data')
        self.assertEqual(result['name'],'vmm-demo');self.assertNotIn('ports',result['services']['db'])
        for php in PHP:
            suffix=php.replace('.','');s=result['services']['php'+suffix]
            self.assertEqual(s['labels']['traefik.http.routers.demo-'+suffix+'.entrypoints'],'php'+suffix)
            self.assertEqual(s['labels']['traefik.http.routers.demo-'+suffix+'-tls.tls'],'true')
            self.assertEqual(s['volumes'][0]['source'],'/data/projects/demo/site')
            self.assertEqual(s['networks'],['default','gateway'])
            self.assertEqual(s['profiles'],['php'+suffix])

    def test_database_admin_is_project_scoped(self):
        for storage in ('files','legacy'):
            p={'slug':'demo','php':'8.4','db_password':'project-secret','db_root_password':'root-secret','storage':storage}
            config=compose(p,'/data');admin=config['services']['phpmyadmin']
            self.assertEqual(admin['environment']['PMA_HOST'],'db')
            self.assertEqual(admin['environment']['PMA_USER'],'website')
            self.assertEqual(admin['environment']['PMA_PASSWORD'],'project-secret')
            self.assertNotIn('root-secret',str(admin))
            self.assertNotIn('ports',admin)
            self.assertEqual(admin['networks'],['default','gateway'])
            self.assertEqual(admin['labels']['traefik.http.routers.demo-database.rule'],'Host(`localhost`) && PathPrefix(`/demo/`)')
            self.assertEqual(admin['labels']['traefik.http.routers.demo-database.entrypoints'],'database')
        second=compose({**p,'slug':'other','db_password':'other-secret'},'/data')
        self.assertNotEqual(config['name'],second['name'])
        self.assertNotEqual(admin['environment']['PMA_PASSWORD'],second['services']['phpmyadmin']['environment']['PMA_PASSWORD'])

    def test_preview_restore_and_admin_links(self):
        p={'slug':'demo','php':'7.4','storage':'files','cms':'joomla','restore':1}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(project_links(p,root)['admin_url'],'http://demo.vmm.test:8074/installation/')
            override=root/'preview.compose.json'
            override.write_text(json.dumps({'services':{'php74':{'ports':[{'target':80,'published':'18074','host_ip':'127.0.0.1','protocol':'tcp'}]}}}))
            links=project_links(p,root)
            self.assertEqual(links['admin_url'],'http://localhost:18074/installation/')
            self.assertIsNone(links['https_url'])
            self.assertEqual(links['frontend_url'],'http://localhost:18074/')
            self.assertEqual(links['backend_url'],'http://localhost:18074/administrator/')
            p['cms']='wordpress'
            self.assertEqual(project_links(p,root)['backend_url'],'http://localhost:18074/wp-admin/')
            p['cms']='joomla'
            p['restore']=0
            self.assertEqual(project_links(p,root)['admin_url'],'http://localhost:18074/administrator/')
            override.write_text(override.read_text().replace('127.0.0.1','0.0.0.0'))
            with self.assertRaises(ValueError): preview_ports(override)

    def test_windows_host_paths(self):
        self.assertEqual(host_path('C:\\VMM\\data'),'/run/desktop/mnt/host/c/VMM/data')
        self.assertEqual(host_path('/Users/a/vmm/data'),'/Users/a/vmm/data')

    def test_legacy_volumes_preserved(self):
        result=compose({'slug':'old','php':'8.4','db_password':'test','db_root_password':'root'},'/data')
        self.assertEqual(result['services']['web']['volumes'],['website:/var/www/html'])

if __name__=='__main__':unittest.main()
