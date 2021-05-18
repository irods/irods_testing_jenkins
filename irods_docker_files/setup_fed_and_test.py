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
import ci_utilities
from subprocess import Popen, PIPE

def get_irods_packages_directory():
    return '/irods_build/' + irods_python_ci_utilities.get_irods_platform_string()

def get_externals_directory():
    return '/irods_externals'

def configure_federation(zone_name):
    disable_client_server_negotiation = False
    irods_version = irods_python_ci_utilities.get_irods_version()
    with open('/zones.json') as f:
        zones = json.load(f)
    if irods_version >= (4,1):
        with open('/etc/irods/server_config.json') as f:
            d = json.load(f)
        if irods_version >= (4,2):
            d['federation'] = zones[zone_name]['federation']
            with open('/etc/irods/server_config.json', 'w') as f:
                json.dump(d, f, indent=4, sort_keys=True)

        configure_zones(d['federation'], disable_client_server_negotiation)
        return(perform_test_setup(d['federation'][0]['zone_name']))

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
        return(create_passthrough_resource())

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
    _rc, _out, _err = irods_python_ci_utilities.subprocess_get_output(['su', '-', 'irods', '-c', 'iadmin addchildtoresc {0} {1}'.format(passthrough_resc, leaf_resc)])
    print('create_passthrough_resource return code', _rc, type(_rc))
    return _rc

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


def check_fed_state(machine_name, database_type):
    is_running = True
    while is_running:
        cmd = ['ping', '-W', '10', '-c', '1', machine_name]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        output, err = proc.communicate()
        _rc = proc.returncode
        if _rc != 0:
            gather_logs(database_type)
            sys.exit(_rc)

def gather_logs(database_type):
    import socket
    output_directory = '/irods_test_env/{0}/{1}/{2}'.format(irods_python_ci_utilities.get_irods_platform_string(),database_type, socket.gethostname())
    irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_directory, lambda x: True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--federation_name', type=str, required=False)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--database_machine', help='database container name', default=None)
    parser.add_argument('--install_externals', action='store_true', default=False)
    parser.add_argument('--test_type', type=str)
    parser.add_argument('--test_name', type=str, default=None)
    parser.add_argument('--zone_name', type=str, required=True)
    parser.add_argument('--remote_zone', type=str, required=True)
    parser.add_argument('--alias_name', type=str, required=True)

    args = parser.parse_args()

    distribution = irods_python_ci_utilities.get_distribution()
    ci_utilities.install_irods_packages(args.database_type, args.database_machine, args.install_externals, get_irods_packages_directory(), get_externals_directory(), is_provider=True)
    ci_utilities.setup_irods(args.database_type, args.zone_name, args.database_machine)
    ci_utilities.start_server(ci_utilities.get_irods_version())

    rc = configure_federation(args.zone_name)
    if args.zone_name == 'tempZone':
        check_fed_state(args.remote_zone, args.database_type)
    else:
        sys.exit(rc)


if __name__ == '__main__':
    main()
