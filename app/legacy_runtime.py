"""Deterministic Compose generation. No shell interpolation of user input."""
import json
import re

PHP = ('8.0', '8.1', '8.2', '8.3', '8.4')

def slug(value):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', value):
        raise ValueError('Projektname: 1–40 Kleinbuchstaben, Ziffern oder Bindestriche; Beginn mit Buchstabe.')
    return value

def ports(version):
    if version not in PHP:
        raise ValueError('PHP-Version wird noch nicht unterstützt.')
    suffix = version.replace('.', '')
    return int('80' + suffix), int('81' + suffix)

def compose(project, host_data):
    name = slug(project['slug'])
    version = project['php']
    ports(version)
    # Each project has its own named volumes and network; no database host ports.
    image = 'wordpress:php' + version + '-apache'
    return {
        'name': 'vmm-' + name,
        'services': {
            'db': {'image': 'mariadb:10.11', 'environment': {
                'MARIADB_DATABASE': 'website', 'MARIADB_USER': 'website',
                'MARIADB_PASSWORD': project['db_password'],
                'MARIADB_ROOT_PASSWORD': project['db_root_password']},
                'volumes': ['database:/var/lib/mysql'],
                'healthcheck': {'test': ['CMD', 'healthcheck.sh', '--connect', '--innodb_initialized'], 'interval': '5s', 'timeout': '5s', 'retries': 30}},
            'web': {'image': image, 'depends_on': {'db': {'condition': 'service_healthy'}},
                'environment': {'WORDPRESS_DB_HOST': 'db', 'WORDPRESS_DB_NAME': 'website',
                    'WORDPRESS_DB_USER': 'website', 'WORDPRESS_DB_PASSWORD': project['db_password']},
                'volumes': ['website:/var/www/html'],
                'networks': ['default', 'gateway'],
                'labels': {'traefik.enable': 'true',
                    'traefik.docker.network': 'vmm-gateway',
                    'traefik.http.routers.' + name + '.rule': 'Host(`' + name + '.vmm.test`)',
                    'traefik.http.routers.' + name + '.entrypoints': 'php' + version.replace('.', ''),
                    'traefik.http.services.' + name + '.loadbalancer.server.port': '80'}}},
        'volumes': {'database': {}, 'website': {}},
        'networks': {'gateway': {'external': True, 'name': 'vmm-gateway'}}}
