import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('php'),'PHP CLI required')
class WordPressLocalOptionsTests(unittest.TestCase):
    def test_license_bridge_keeps_database_options_and_exports_no_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tools=root/'tools';tools.mkdir();mu=root/'mu';mu.mkdir()
            for name in ('extension-bridge.php','wordpress-extension-updates.php'):
                shutil.copyfile(ROOT/'app/tools'/name,tools/name)
            runner=tools/'runner.php'
            runner.write_text('''<?php
function get_option($name,$default=[]){return $name==='license_option'?['original'=>'kept']:$default;}
function update_option(){throw new Exception('Database options must not be modified');}
function delete_site_transient($name){}
function wp_mkdir_p($path){mkdir($path,0777,true);}
define('WPMU_PLUGIN_DIR',$argv[1]);
require __DIR__.'/extension-bridge.php';
''')
            payload={'source':{'id':'test','element':'theme','cms_config':{'wordpress_options':{'license_option':{'key':'key'}}}},'credentials':{'key':'local-key'}}
            subprocess.run(['php',str(runner),str(mu)],input=json.dumps(payload),text=True,capture_output=True,check=True)
            values=json.loads((tools/'wordpress-local-options.json').read_text())
            self.assertEqual(values['license_option'],{'original':'kept','key':'local-key'})
            plugin=(mu/'vmm-extension-updates.php').read_text()
            self.assertNotIn('local-key',plugin)
            self.assertNotIn('__VMM_LOCAL_OPTIONS_FILE__',plugin)
            self.assertIn('pre_option_',plugin)
