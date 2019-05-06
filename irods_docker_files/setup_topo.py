#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import sys
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
    print('stderr ' , _err)
    #cmd = ['docker', 'network', 'connect', 'bridge', machine_name]
    #p = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
    #out, err = p.communicate()
    #print('stderr ', err)
    
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
            sys.exit(_ec)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--is_consumer', action='store_true', default=False)
    parser.add_argument('--consumer_name', type=str)
    parser.add_argument('--provider_name', type=str, required=True)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--test_type', type=str)
    parser.add_argument('--test_name', type=str)
    parser.add_argument('--network_name', type=str, required=True)
    parser.add_argument('--alias_name', type=str, required=True)

    args = parser.parse_args()
   
    distribution = irods_python_ci_utilities.get_distribution()
    install_and_setup(args.database_type)

    if args.is_consumer:
        print('let us set the consumer up')
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
        start_database(args.database_type, distribution)
        setup_irods(args.database_type)
        if args.test_type == 'topology_icat':
            check_ports_open('resource1.example.org')
            rc = run_tests(args.test_type, args.test_name)
            sys.exit(rc)
        else:
            check_ports_open('resource1.example.org')
            check_topo_state(args.consumer_name)

    subprocess.check_call(['tail -f /dev/null'], shell=True)

if __name__ == '__main__':
    main()
