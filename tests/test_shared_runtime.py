import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from runtime import PHP
from shared_runtime import stack, database_info, write_config

class SharedRuntimeTests(unittest.TestCase):
    def test_one_service_per_php_and_no_published_database(self):
        cfg=stack('/data','root-test')
        self.assertEqual(set(cfg['services']),{'db','phpmyadmin'}|{'php'+v.replace('.','') for v in PHP})
        self.assertNotIn('ports',cfg['services']['db'])
        self.assertNotIn('ports',cfg['services']['phpmyadmin'])
        for version in PHP:
            service=cfg['services']['php'+version.replace('.','')]
            self.assertNotIn('root-test',str(service))
            self.assertIn('/data/projects:/vmm-projects',service['volumes'])

    def test_project_databases_are_distinct_and_names_safe(self):
        a=database_info({'slug':'my-site','db_password':'secret'})
        b=database_info({'slug':'other','db_password':'other-secret'})
        self.assertEqual(a['database'],'vmm_my_site')
        self.assertEqual(a['user'],a['database'])
        self.assertNotEqual(a['database'],b['database'])
        with self.assertRaises(ValueError):database_info({'slug':'../escape','db_password':'x'})

    def test_vhosts_default_deny_and_projects_always_reachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p={'slug':'demo','storage':'shared','db_password':'test'}
            path=write_config(root,'/host-data',[p])
            self.assertIn('Require all denied',(root/'shared/apache/000-default.conf').read_text())
            host=(root/'shared/apache/demo.conf').read_text()
            self.assertIn('DocumentRoot "/vmm-projects/demo/site"',host)
            self.assertNotIn('.enabled',host)
            self.assertNotIn('[R=503,L]',host)
            cfg=(root/'shared/pma/config.php').read_text()
            self.assertNotIn("HTTP_X_FORWARDED_PREFIX",cfg)
            self.assertIn("'user'=>'root'",cfg)
            self.assertNotIn('only_db',cfg)
            self.assertNotIn('root_password',cfg)
            self.assertEqual(json.loads(path.read_text())['name'],'vmm-runtime')

    def test_cms_database_rewrite_preserves_non_database_configuration(self):
        import shared_operations
        import operations
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'site').mkdir();(root/'tools').mkdir()
            conf=root/'site/configuration.php'
            conf.write_text("<?php class JConfig {public $host='db';public $user='website';public $db='website';public $password='old';public $mailonline=false;public $tmp_path='/var/www/html/tmp';}")
            with patch.object(operations,'folder',return_value=root):
                shared_operations.rewrite_database({'slug':'example','storage':'shared','db_password':'new'})
            content=conf.read_text()
            self.assertIn("$db='vmm_example'",content)
            self.assertIn('$mailonline=false',content)
            self.assertIn('/vmm-projects/example/site/tmp',content)
            self.assertEqual(json.loads((root/'tools/database.json').read_text())['user'],'vmm_example')
