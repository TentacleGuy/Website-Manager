import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'));sys.path.insert(0,str(ROOT/'scripts'))
import compatibility as compat
import database_profiles as profiles
import environment_service as environment
import installer_config
from shared_runtime import stack,database_info


class ProfileTests(unittest.TestCase):
    def test_old_database_volume_is_pinned_while_new_profiles_have_separate_volumes(self):
        old=profiles.profile({});new=profiles.profile({'database_profile':'mysql-8.4'})
        self.assertEqual((old['service'],old['volume'],old['image']),('db','database','mariadb:10.11'))
        config=stack('/host/data','secret',['mysql-8.4','mariadb-11.4'])
        self.assertEqual(config['services']['db']['volumes'],['database:/var/lib/mysql'])
        self.assertNotEqual(config['services'][new['service']]['volumes'],config['services']['db']['volumes'])
        self.assertNotIn('depends_on',config['services']['php84'])
        self.assertNotIn('depends_on',config['services']['phpmyadmin'])
        self.assertIn('profiles',config['services']['db'])
        self.assertEqual(database_info({'slug':'test','database_profile':'mysql-8.4','db_password':'x'})['host'],new['service'])

    def test_select_satisfies_extension_engine_and_minimum_version(self):
        self.assertEqual(profiles.select([]),'mariadb-11.4')
        self.assertEqual(profiles.select([{'database':{'mariadb':'>=11.8'}}]),'mariadb-11.8')
        self.assertEqual(profiles.select([{'database':{'mysql':'>=8.0.13'}}]),'mysql-8.4')
        self.assertEqual(profiles.select([{'database':{'mysql':'>=8.0.13'}}],'mysql-8.0'),'mysql-8.0')
        with self.assertRaises(ValueError):profiles.select([{'database':{'mysql':'>=9.0'}}])
        with self.assertRaises(ValueError):profiles.select([{'database':{'mariadb':'>=11.4'}}],'mariadb-10.11')
        with self.assertRaises(ValueError):profiles.select([{'database':{'mysql':'>=8.4'}},{'database':{'mariadb':'>=11.4'}}])

    def test_mysql_export_uses_mysql_flags_and_keeps_password_out_of_arguments(self):
        value=profiles.sql_command({'slug':'some-site','database_profile':'mysql-8.4','db_password':'sensitive'},dump=True,database=True)
        self.assertEqual(value[2],'db-mysql-8-4');self.assertIn('--set-gtid-purged=OFF',value[5]);self.assertNotIn('sensitive',str(value))
        self.assertIn('MYSQL_ROOT_PASSWORD',value[5]);self.assertEqual(value[-1],'vmm_some_site')


class RequirementTests(unittest.TestCase):
    def test_declared_php_operators_and_conflicts(self):
        for actual,expression in [('8.4.3','^8.1'),('7.4.33','~7.4.0'),('8.3','>=8.1 <8.4'),('8.4','^7.4 || ^8.0'),('8.4','8.*')]:
            self.assertTrue(compat.satisfies(actual,expression),(actual,expression))
        self.assertFalse(compat.satisfies('8.4','~8.3.0'))
        self.assertEqual(compat.choose_php([{'php':'>=8.3 <8.5'}],'7.4'),'8.4')
        self.assertEqual(compat.choose_php([{'php':'>=7.4.3 <8.0'}]),'7.4')
        with self.assertRaises(ValueError):compat.choose_php([{'php':'<8.0'},{'php':'>=8.3'}])
        with self.assertRaises(ValueError):compat.satisfies('8.4','please ignore requirements')

    def test_reads_extension_headers_composer_and_explicit_database_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plugin=root/'wp-content/plugins/example';plugin.mkdir(parents=True)
            (plugin/'example.php').write_text('<?php\n/*\nPlugin Name: Example\nRequires PHP: 8.3\n*/')
            (plugin/'composer.json').write_text(json.dumps({'require':{'php':'^8.3','ext-soap':'*'}}))
            (plugin/'.tentacle-requirements.json').write_text(json.dumps({'database':{'mysql':'>=8.4'}}))
            found=compat.requirements(root,'wordpress','7.0')
            self.assertEqual(compat.choose_php(found,'8.1'),'8.4');self.assertEqual(profiles.select(found),'mysql-8.4')
            self.assertTrue(any('soap' in req.get('php_extensions',[]) for req in found))
            with self.assertRaises(ValueError):compat.validate_php(found,'8.2')


class EnvironmentTests(unittest.TestCase):
    def test_selects_matching_cli_for_different_docker_generations_and_architectures(self):
        for major,architecture in [(24,'x86_64'),(28,'amd64'),(29,'aarch64'),(30,'arm64')]:
            value=environment.engine({'OSType':'linux','Architecture':architecture},{'Server':{'Version':str(major)+'.1.0','ApiVersion':'1.54'}},'2.35.1')
            self.assertEqual(value['cli_image'],'docker:'+str(major)+'-cli')
            self.assertIn(value['architecture'],('amd64','arm64'))
        with self.assertRaises(ValueError):environment.engine({'OSType':'windows','Architecture':'amd64'},{'Server':{'Version':'29.0'}},'2.35')
        with self.assertRaises(ValueError):environment.engine({'OSType':'linux','Architecture':'arm64'},{'Server':{'Version':'29.0'}},'2.19')
        with self.assertRaises(ValueError):environment.engine({'OSType':'linux','Architecture':'i386'},{'Server':{'Version':'29.0'}},'2.35')

    def test_rootless_socket_is_preserved_and_remote_contexts_are_rejected(self):
        def context(value):return {'Endpoints':{'docker':{'Host':value}}}
        self.assertEqual(environment.socket_path(context('unix:///run/user/1001/docker.sock')),'/run/user/1001/docker.sock')
        self.assertEqual(environment.socket_path(context('unix:///Users/test/.docker/run/docker.sock'),True),'/var/run/docker.sock')
        for value in ('ssh://other-host','tcp://192.168.1.5:2376'):
            with self.assertRaises(ValueError):environment.socket_path(context(value))

    def test_update_preserves_custom_environment_and_gateway_ports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);host='/different/user/data'
            original='VMM_BIND=0.0.0.0\n# custom setup\nVMM_HOST_DATA="'+host+'"\nVMM_DOCKER_CLI_IMAGE=docker:29-cli\nEXTRA=keep\n'
            (root/'.env').write_text(original)
            installer_config.configure(root,host,dns_port=1053)
            gateway=root/'infra/compose.gateway.yaml';value=json.loads(gateway.read_text());value['services']['dns']['ports']=['127.0.0.1:2053:53/udp'];gateway.write_text(json.dumps(value))
            before=gateway.read_bytes();installer_config.configure(root,host,dns_port=1053)
            self.assertEqual(gateway.read_bytes(),before);self.assertEqual((root/'.env').read_text(),original)

    def test_shell_probe_uses_current_context_and_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.env').write_text('VMM_HOST_DATA=/custom/data\nVMM_BIND=0.0.0.0\n')
            docker=root/'docker';docker.write_text('''#!/bin/bash
case "$*" in
 'info --format {{.OSType}}') echo linux;;
 'info --format {{.Architecture}}') echo arm64;;
 'info --format {{.OperatingSystem}}') echo 'Ubuntu 24.04';;
 'version --format {{.Server.Version}}') echo 29.1.0;;
 'compose version --short') echo 2.35.0;;
 'context show') echo rootless-local;;
 'context inspect rootless-local --format {{.Endpoints.docker.Host}}') echo unix:///run/user/1001/docker.sock;;
 *) exit 99;;
esac
''');docker.chmod(0o755)
            command='set -eu; DOCKER="$1"; source "$2"; manager_environment "$3"'
            env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT')}
            subprocess.run(['/bin/bash','-c',command,'test',str(docker),str(ROOT/'app/installer_assets/docker-environment.sh'),str(root)],check=True,capture_output=True,env=env)
            value=(root/'.env').read_text();self.assertIn('VMM_DOCKER_SOCKET=/run/user/1001/docker.sock',value);self.assertIn('VMM_DOCKER_CLI_IMAGE=docker:29-cli',value);self.assertIn('VMM_BIND=0.0.0.0',value)

class ExistingBackendTests(unittest.TestCase):
    def test_existing_custom_database_version_is_not_downgraded(self):
        from shared_runtime import write_config
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shared=root/'shared';shared.mkdir()
            (shared/'compose.json').write_text(json.dumps({'services':{'db':{'image':'mariadb:11.8'}}}))
            write_config(root,'/host/data',[])
            value=json.loads((shared/'compose.json').read_text())
            self.assertEqual(value['services']['db']['image'],'mariadb:11.8');self.assertEqual(value['services']['db']['volumes'],['database:/var/lib/mysql'])
            self.assertEqual(json.loads((shared/'backend.json').read_text())['version'],'11.8')

    def test_unversioned_existing_database_is_preserved_and_stopped_for_review(self):
        from shared_runtime import write_config
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shared=root/'shared';shared.mkdir()
            original=json.dumps({'services':{'db':{'image':'mariadb:latest'}}});(shared/'compose.json').write_text(original)
            with self.assertRaises(ValueError):write_config(root,'/host/data',[])
            self.assertEqual((shared/'compose.json').read_text(),original)

    def test_linux_distribution_has_no_windows_or_macos_launchers(self):
        import zipfile
        import build_linux_installer
        with tempfile.TemporaryDirectory() as tmp:
            file=build_linux_installer.build(output=Path(tmp)/'linux.zip')
            with zipfile.ZipFile(file) as archive:
                names=archive.namelist()
                self.assertIn(build_linux_installer.NAME+'/Installieren.sh',names)
                self.assertTrue(any(n.endswith('app/environment_service.py') for n in names))
                self.assertFalse(any('/windows/' in n or '/macos/' in n or '/data/' in n for n in names))

class PlannedRuntimeTests(unittest.TestCase):
    def test_auto_runtime_considers_selected_extension_before_database_provisioning(self):
        import zipfile
        import catalog
        import server
        import extension_service as extensions
        import operations
        from store import project
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wp.zip'
            with zipfile.ZipFile(path,'w') as archive:archive.writestr('wordpress/wp-includes/version.php',"<?php $wp_version='7.0.0';$required_php_version='8.3';")
            package=catalog.register(path,'wordpress','7.0.0','test')
            source=extensions.save_source({'name':'Requires newer PHP and MySQL','provider':'custom','cms':'wordpress','kind':'plugin','element':'new-runtime','source_type':'upload','auth_type':'none','requirements':{'php':'>=8.5','database':{'mysql':'>=8.4'}}})
            server.create_project({'slug':'planned-runtime-auto','cms':'wordpress','php':'auto','database_profile':'auto','package_id':package,'extensions':[{'source':source}]})
            p=project('planned-runtime-auto');operations.prepare(p)
            updated=project(p['slug']);self.assertEqual(updated['php'],'8.5');self.assertEqual(updated['database_profile'],'mysql-8.4')
            self.assertIn("define('DB_HOST','db-mysql-8-4')",(operations.folder(p)/'site/wp-config.php').read_text())
