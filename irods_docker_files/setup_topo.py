#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import sys
import irods_python_ci_utilities
import subprocess
import shutil
import ci_utilities
import time
from subprocess import Popen, PIPE

def get_irods_packages_directory():
    return '/irods_build/' + irods_python_ci_utilities.get_irods_platform_string()

def setup_irods(database_type):
    if database_type == 'postgres':
        p = subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input'], shell=True)

def check_ports_open(machine_name):
    listen_cmd = ['nc', '-vz', machine_name, '1247']
    status = 'refused'
    while status == 'refused':
        proc = subprocess.Popen(listen_cmd, stdout = PIPE, stderr = PIPE)
        _out, _err = proc.communicate()
        print('_err ', _err)
        if 'open' in (_err):
            status = 'open'
        if not 'Connection refused' in (_err):
            status = 'open'
        time.sleep(1)
        print('status ', status)

    return status

def setup_consumer():
    check_ports_open('icat.example.org')
    p = subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /tmp/irods_consumer.input'], shell=True)

def connect_to_network(machine_name, alias_name, network_name):
    network_cmd = ['docker', 'network', 'connect', '--alias', alias_name, network_name, machine_name]
    proc = Popen(network_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = proc.communicate()
    
def run_tests(test_type, test_name):
    print("let's try to run tests")
    _rc, _out, _err = irods_python_ci_utilities.subprocess_get_output(['python run_tests_in_zone.py --test_type {0} --specific_test {1}'.format(test_type, test_name)], shell=True, check_rc=True)
    return _rc

def check_topo_state(machine_name):
    is_running = True
    while is_running:
        cmd = ['docker', 'inspect', '--format', '{{.State.Running}}', machine_name]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        output, err = proc.communicate()
        if 'false' in output:
            exit_code = ['docker', 'inspect', '--format', '{{.State.ExitCode}}', machine_name]
            ec_proc = Popen(exit_code, stdout=PIPE, stderr=PIPE)
            _out, _err = ec_proc.communicate()
            _out_split = _out.split('/')
            _ec = int(_out_split[0])
            return _ec
            sys.exit(_ec)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--is_consumer', action='store_true', default=False)
    parser.add_argument('--consumer_name', type=str)
    parser.add_argument('--provider_name', type=str, required=True)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--install_externals', action='store_true', default=False)
    parser.add_argument('--test_type', type=str)
    parser.add_argument('--test_name', type=str)
    parser.add_argument('--network_name', type=str, required=True)
    parser.add_argument('--alias_name', type=str, required=True)

    args = parser.parse_args()
   
    distribution = irods_python_ci_utilities.get_distribution()
    ci_utilities.install_irods_packages(args.database_type, args.install_externals, get_irods_packages_directory())

    if args.is_consumer:
        connect_to_network(args.consumer_name, args.alias_name, args.network_name)
        setup_consumer()
        if args.test_type == 'topology_resource':
            check_ports_open('icat.example.org')
            rc = run_tests(args.test_type, args.test_name)
            sys.exit(rc)
        else:
            check_ports_open('icat.example.org')
            check_topo_state(args.provider_name)
    else:
        connect_to_network(args.provider_name, args.alias_name, args.network_name)
        setup_irods(args.database_type)
        if args.test_type == 'topology_icat':
            check_ports_open('resource1.example.org')
            rc = run_tests(args.test_type, args.test_name)
            sys.exit(rc)
        else:
            check_ports_open('resource1.example.org')
            check_topo_state(args.consumer_name)


if __name__ == '__main__':
    main()
