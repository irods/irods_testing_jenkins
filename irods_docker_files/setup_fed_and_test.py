#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import sys
import json
import irods_python_ci_utilities
import subprocess
import shutil
import time
from subprocess import Popen, PIPE

def get_irods_packages_directory():
    return '/irods_build/' + irods_python_ci_utilities.get_irods_platform_string()

def install_and_setup(database_type):
    irods_packages_directory = get_irods_packages_directory()
    if os.path.exists(irods_packages_directory):
        icat_package_basename = filter(lambda x:'irods-server' in x, os.listdir(irods_packages_directory))[0]
        if 'irods-server' in icat_package_basename:
            server_package = os.path.join(irods_packages_directory, icat_package_basename)
            runtime_package = server_package.replace('irods-server', 'irods-runtime')
            icommands_package = server_package.replace('irods-server', 'irods-icommands')
            irods_python_ci_utilities.install_os_packages_from_files([runtime_package, icommands_package, server_package])
        else:
            raise RuntimeError('unhandled package name')

        install_database_plugin(irods_packages_directory, database_type)
   
def install_database_plugin(irods_packages_directory, database_type):
    package_filter = 'irods-database-plugin-' + database_type
    database_plugin_basename = filter(lambda x:package_filter in x, os.listdir(irods_packages_directory))[0]
    database_plugin = os.path.join(irods_packages_directory, database_plugin_basename)
    irods_python_ci_utilities.install_os_packages_from_files([database_plugin])

def start_database(database_type, distribution):
    if database_type == 'postgres' and distribution == 'Ubuntu':
        start_db = subprocess.Popen(['service', 'postgresql', 'start'])
        start_db.wait()
        status = 'no response'
        while status == 'no response':
            status_db = subprocess.Popen(['pg_isready'], stdout=PIPE, stderr=PIPE)
            out, err = status_db.communicate()
            if 'accepting connections' in out:
                status = out
    elif database_type == 'postgres' and distribution == 'Centos linux':
        start_db = subprocess.Popen(['su', '-', 'postgres', '-c', "pg_ctl -D /var/lib/pgsql/data -l logfile start"])
        start_db.wait()
        rc = 1
        while rc != 0:
            rc, stdout, stderr = irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "psql ICAT -c '\d'>/dev/null 2>&1"])
            time.sleep(1)

def setup_irods(database_type, zone_name):
    if database_type == 'postgres':
        if zone_name == 'tempZone':
            p = subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input'], shell=True)
        else:
            p = subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /tmp/other_zone.input'], shell=True)
    print("irods setup successful")

def configure_federation(zone_name):
    disable_client_server_negotiation = False
    irods_version = irods_python_ci_utilities.get_irods_version()
    with open('/tmp/zones.json') as f:
        zones = json.load(f)
    if irods_version >= (4,1):
        with open('/etc/irods/server_config.json') as f:
            d = json.load(f)
        if irods_version >= (4,2):
            d['federation'] = zones[zone_name]['federation']
            with open('/etc/irods/server_config.json', 'w') as f:
                json.dump(d, f, indent=4, sort_keys=True)

        configure_zones(d['federation'], disable_client_server_negotiation)
        perform_test_setup(d['federation'][0]['zone_name'])

def configure_zones(federation, disable_client_server_negotiation):
    for f in federation:
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin mkzone {0} remote {1}:{2}'.format(f['zone_name'], f['icat_host'], f['zone_port'])], check_rc=True)
        if f['zone_name'] == 'tempZone':
            sqlQuery = 'select alias, sqlStr from R_SPECIFIC_QUERY'
            irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', "iadmin asq '{sqlQuery}' bug_3466_query".format(**locals())], check_rc=True)

    if disable_client_server_negotiation and irods_python_ci_utilities.get_irods_version() >= (4, 1):
        with open('/var/lib/irods/.irods/irods_environment.json') as f:
            d = json.load(f)
        d['irods_client_server_negotiation'] = 'off'
        with open('/var/lib/irods/.irods/irods_environment.json', 'w') as f:
            json.dump(d, f, indent=4, sort_keys=True)
    # reServer requires restart, possibly for server_config reload
    if federation:
        if irods_python_ci_utilities.get_irods_version()[0:2] < (4, 2):
            irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/iRODS/irodsctl stop'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/iRODS/irodsctl start'], check_rc=True)
        else:
            irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/irodsctl stop'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/irodsctl start'], check_rc=True)

def perform_test_setup(zone_name):
    username = 'zonehopper#{0}'.format(zone_name)
    create_user(username)
    if irods_python_ci_utilities.get_irods_version() >= (4,):
        create_passthrough_resource()

def create_user(username):
    irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin mkuser {0} rodsuser'.format(username)], check_rc=True)

def create_passthrough_resource():
    import socket
    hostname = socket.gethostname()
    passthrough_resc = 'federation_remote_passthrough'
    leaf_resc = 'federation_remote_unixfilesystem_leaf'
    leaf_resc_vault = os.path.join('/tmp', leaf_resc)
    irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin mkresc {0} passthru'.format(passthrough_resc)], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin mkresc {0} unixfilesystem {1}:{2}'.format(leaf_resc, hostname, leaf_resc_vault)], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin addchildtoresc {0} {1}'.format(passthrough_resc, leaf_resc)], check_rc=True)


def connect_to_network(machine_name, alias_name, network_name):
    network_cmd = ['docker', 'network', 'connect', '--alias', alias_name, network_name, machine_name]
    proc = Popen(network_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = proc.communicate()
    
def run_tests(zone_name, remote_zone, test_type, test_name):
    if zone_name == 'otherZone':
        remote_version_cmd = ['docker', 'exec', remote_zone, 'python', 'get_irods_version.py']
        remote_irods_version = None
        while remote_irods_version == None:
            proc = subprocess.Popen(remote_version_cmd, stdout = PIPE, stderr = PIPE)
            _out, _err = proc.communicate()
            if _out is not None or _out != 'None':
                remote_irods_version = _out
            time.sleep(1)

        irods_version = remote_irods_version.split('\n')[0].split('(')[1].split(')')[0].replace(', ','.')
        federation_args = ' '.join([irods_version, 'tempZone', 'icat.tempZone.example.org'])
        _rc, _out, _err = irods_python_ci_utilities.subprocess_get_output( ['python run_tests_in_zone.py --test_type {0} --specific_test {1} --federation_args {2}'.format(test_type, test_name, federation_args)], shell=True, check_rc=True)
        return _rc

def check_fed_state(machine_name):
    is_running = True
    while is_running:
        cmd = ['docker', 'inspect', '--format', '{{.State.Running}}', machine_name]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        output, err = proc.communicate()
        if 'false' in output:
            is_running = False
            exit_code = ['docker', 'inspect', '--format', '{{.State.ExitCode}}', machine_name]
            ec_proc = Popen(exit_code, stdout=PIPE, stderr=PIPE)
            _out, _err = ec_proc.communicate()
            _out_split = _out.split('/')
            _ec = int(_out_split[0])
            return _ec
        time.sleep(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--federation_name', type=str, required=True)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--test_type', type=str)
    parser.add_argument('--test_name', type=str, default=None)
    parser.add_argument('--network_name', type=str, required=True)
    parser.add_argument('--zone_name', type=str, required=True)
    parser.add_argument('--remote_zone', type=str, required=True)
    parser.add_argument('--alias_name', type=str, required=True)

    args = parser.parse_args()
   
    distribution = irods_python_ci_utilities.get_distribution()
    install_and_setup(args.database_type)

    connect_to_network(args.federation_name, args.alias_name, args.network_name)
    start_database(args.database_type, distribution)
    setup_irods(args.database_type, args.zone_name)
    configure_federation(args.zone_name)
    if args.zone_name == 'otherZone':
        rc = run_tests(args.zone_name, args.remote_zone, args.test_type, args.test_name)
        sys.exit(rc)
    else:
        rc = check_fed_state(args.remote_zone)
        sys.exit(rc)

    subprocess.check_call(['tail -f /dev/null'], shell=True)

if __name__ == '__main__':
    main()
