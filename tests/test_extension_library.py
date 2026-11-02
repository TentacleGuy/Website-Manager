"""Library behaviour with isolated files and native updater fixtures; no vendor traffic."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
if 'store' not in sys.modules:
    _isolated=tempfile.TemporaryDirectory(prefix='library-tests-')
    os.environ['VMM_DATA']=_isolated.name
import extension_service as ext
import extension_library as lib
import server
from store import db


class LibraryTests(unittest.TestCase):
    def zip(self,name='Example Plugin',slug='example-plugin',v='1.2.3',extra=''):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'upload.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr(slug+'/'+slug+'.php','<?php /*\nPlugin Name: '+name+'\nVersion: '+v+'\nAuthor: Example Author\n'+extra+'\n*/')
        return path

    def test_upload_detects_and_reuses_source_and_does_not_guess_external_uri(self):
        path=self.zip(slug='library-external',extra='Update URI: https://premium.example/plugin')
        with patch('extension_service.remote') as remote:
            one=lib.upload(path);two=lib.upload(path)
            remote.assert_not_called()
        self.assertEqual(one['source'],two['source']);self.assertEqual(one['id'],two['id'])
        self.assertEqual(ext.source(one['source'])['source_type'],'upload')

    def test_wordpress_org_identity_must_match_name_and_author(self):
        info=ext.inspect_upload(self.zip())
        data={'name':'Example Plugin','author':'<a>Example Author</a>','download_link':'https://downloads.wordpress.org/plugin/example-plugin.zip'}
        with patch('extension_service.remote',return_value=io.BytesIO(json.dumps(data).encode())):
            self.assertEqual(lib.detect_origin(info)['source_type'],'wordpress_org')
        data['author']='Someone else'
        with patch('extension_service.remote',return_value=io.BytesIO(json.dumps(data).encode())):
            self.assertEqual(lib.detect_origin(info)['source_type'],'upload')

    def test_delete_archive_retains_installed_metadata_and_reupload_creates_archive(self):
        with patch('extension_service.remote',side_effect=ValueError('offline')):
            item=lib.upload(self.zip(slug='library-delete'))
        ident=item['id'];_,path=lib.package_file(ident)
        self.assertTrue(path.is_file());lib.delete_package(ident);self.assertFalse(path.exists())
        with db() as c:row=c.execute('SELECT archived FROM extensions WHERE id=?',(ident,)).fetchone()
        self.assertEqual(row['archived'],0)
        with self.assertRaises(ValueError):lib.package_file(ident)
        with patch('extension_service.remote',side_effect=ValueError('offline')):
            again=lib.upload(self.zip(slug='library-delete'))
        self.assertNotEqual(again['id'],ident)
        self.assertEqual(again['source'],item['source'])

    def test_busy_package_is_not_deleted(self):
        with patch('extension_service.remote',side_effect=ValueError('offline')):item=lib.upload(self.zip(slug='library-busy'))
        with db() as c:c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('library-delete-busy','extension-'+item['source'],'download','running','Test',1,None))
        try:
            with self.assertRaises(ValueError):lib.delete_package(item['id'])
            self.assertTrue(lib.package_file(item['id'])[1].exists())
        finally:
            with db() as c:c.execute("DELETE FROM jobs WHERE id='library-delete-busy'")

    def test_global_key_does_not_rewrite_shared_legacy_license(self):
        with patch('extension_service.remote',side_effect=ValueError('offline')):item=lib.upload(self.zip(slug='library-key'))
        ident=item['source'];s=ext.source(ident)
        shared=ext.save_license({'provider':s['provider'],'label':'Shared legacy','key':'keep-shared'})
        ext.save_source({**s,'license':shared})
        lib.edit(ident,{'name':'New Name','key':'global-specific'})
        current=ext.source(ident)
        self.assertNotEqual(shared,current['license'])
        self.assertEqual(ext.resolve_license(shared)['key'],'keep-shared')
        self.assertEqual(ext.resolve_license(current['license'])['source'],ident)
        self.assertEqual(ext.resolve_license(current['license'])['key'],'global-specific')

    def make_project(self,name):
        with db() as c:c.execute('INSERT OR REPLACE INTO projects (slug,cms,php,status,created,restore,storage) VALUES (?,?,?,?,?,?,?)',(name,'wordpress','8.4','running',1,0,'shared'))

    def test_project_credentials_are_scoped_and_public_candidates_exclude_secrets(self):
        name='library-origin';self.make_project(name)
        row={'key':'plugin:wpml/sitepress.php','name':'WPML','cms':'wordpress','kind':'plugin','element':'wpml','version':'4.0','latest':'5.0','can_download':True,'origin':'OTGS Installer','has_key':True,'license_key':'site-secret','url':'https://vendor.example/pkg?site_key=site-secret'}
        with patch('extension_library.bridge',return_value=[row]):
            public=lib.candidates(name)
            self.assertNotIn('site-secret',json.dumps(public));self.assertNotIn('url',public[0])
            lib.import_project(name,row['key'],False)
        source=next(s for s in ext.sources() if s['element']=='wpml')
        self.assertFalse(source.get('license'))
        own=next(l for l in ext.licenses() if l.get('source')==source['id'])
        self.assertEqual(own['project'],name);self.assertEqual(own['key'],'site-secret')
        lib.project_key(name,source['id'],{'key':''})
        self.assertFalse(any(l.get('source')==source['id'] and l.get('project')==name for l in ext.licenses()))

    def test_project_source_refreshes_and_does_not_store_signed_urls(self):
        name='library-dynamic';self.make_project(name)
        ident=ext.save_source({'provider':'custom','name':'Dynamic','cms':'wordpress','kind':'plugin','element':'dynamic','source_type':'project','origin_project':name,'origin_key':'plugin:dynamic/dynamic.php','auth_type':'none'})
        with patch('extension_library.bridge',return_value={'latest':'2.0','url':'https://vendor.example?key=secret'}) as native:
            ext.check(ident)
            native.assert_called_once()
        self.assertNotIn('secret',json.dumps(ext.source(ident)['available']))
        self.assertEqual(ext.source(ident)['available'][0]['version'],'2.0')

    def test_download_rejects_wrong_package_identity_and_cleans_temp_file(self):
        name='library-wrong-package';self.make_project(name)
        s={'cms':'wordpress','kind':'plugin','element':'expected','origin_project':name,'origin_key':'plugin:expected/expected.php'}
        token='e'*24;folder=lib.DATA/'projects'/name/'tools';folder.mkdir(parents=True,exist_ok=True)
        target=folder/('library-'+token+'.zip');target.write_bytes(self.zip(slug='different').read_bytes())
        with patch('extension_library.bridge',return_value={'latest':'1.2.3','token':token}):
            with self.assertRaisesRegex(ValueError,'passt nicht'):lib.release(s,True)
        self.assertFalse(target.exists())

    def test_joomla_template_identity_and_update_xml_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'template.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('templateDetails.xml','<extension type="template"><name>shaper_resort</name><version>3.1.1</version><updateservers><server>https://updates.example/template.xml</server></updateservers></extension>')
            value=ext.inspect_upload(p)
        self.assertEqual(value['element'],'shaper_resort');self.assertEqual(value['source_type'],'update_xml');self.assertEqual(value['kind'],'theme')


class NativeWpmlBridgeTests(unittest.TestCase):
    def test_otgs_private_settings_method_is_never_called(self):
        import shutil
        import subprocess
        php=shutil.which('php')
        if not php:self.skipTest('PHP runtime unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            includes=root/'wp-admin/includes';includes.mkdir(parents=True)
            for name in ('plugin.php','plugin-install.php','file.php'):(includes/name).write_text('<?php')
            shutil.copyfile(Path(__file__).resolve().parents[1]/'app/tools/library-project.php',root/'native.php')
            wrapper=root/'test.php'
            wrapper.write_text("""<?php
            define('ABSPATH',__DIR__.'/');
            function get_plugins(){return ['sitepress-multilingual-cms/sitepress.php'=>['Name'=>'WPML Multilingual CMS','Version'=>'4.8.0']];}
            function get_site_transient($key){return (object)['response'=>[], 'no_update'=>[]];}
            function set_site_transient($key,$value){}
            function wp_update_plugins(){}
            function wp_update_themes(){}
            function wp_get_themes(){return [];}
            class FakeInstaller {
                private function settings(){throw new Exception('Must not call a private method');}
                public function get_settings(){return ['repositories'=>['wpml'=>['data'=>['downloads'=>['plugins'=>['sitepress-multilingual-cms'=>['name'=>'WPML Multilingual CMS']]]]]]];}
                public function get_repository_site_key($repo){return 'FAKE-SITE-KEY';}
                public function refresh_repositories_data(){}
            }
            function WP_Installer(){return new FakeInstaller;}
            function plugins_api($action,$args){return (object)['name'=>'WPML Multilingual CMS','version'=>'4.9.3','download_link'=>'https://vendor.example/wpml.zip?site_key=fake'];}
            function is_wp_error($value){return false;}
            function wp_strip_all_tags($value){return strip_tags($value);}
            require __DIR__.'/native.php';
            """)
            result=subprocess.run([php,str(wrapper)],input=json.dumps({'action':'list'}).encode(),capture_output=True,check=True)
            rows=json.loads(result.stdout.decode().split('VMM_LIBRARY_JSON:')[1])
            self.assertEqual(rows[0]['origin'],'OTGS Installer · wpml')
            self.assertTrue(rows[0]['can_download']);self.assertTrue(rows[0]['has_key'])
            result=subprocess.run([php,str(wrapper)],input=json.dumps({'action':'resolve','key':'plugin:sitepress-multilingual-cms/sitepress.php'}).encode(),capture_output=True,check=True)
            data=json.loads(result.stdout.decode().split('VMM_LIBRARY_JSON:')[1])
            self.assertEqual(data['latest'],'4.9.3')
            self.assertNotIn('site_key',json.dumps(data))
