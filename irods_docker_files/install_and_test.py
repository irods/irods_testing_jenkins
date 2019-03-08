#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import sys
import irods_python_ci_utilities
import subprocess
import shutil
import time
from subprocess import PIPE

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

def start_database(database_type):
    distribution = irods_python_ci_utilities.get_distribution()
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

def run_test(test_name, output_root_directory):
    try:
        test_output_file = '/var/lib/irods/log/test_output.log'
        rc, stdout, stderr = irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'cd scripts; python2 run_tests.py --xml_output --run_s={0} 2>&1 | tee {1}; exit $PIPESTATUS'.format(test_name, test_output_file)])
        return rc
    finally:
        output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(),test_name)
        #output_directory = output_root_directory + '/' + test_name
        irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_directory, lambda x: True)
        shutil.copy('/var/lib/irods/log/test_output.log', output_directory)
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-t', '--test_name', help='test name')

    args = parser.parse_args()
    print('-d ', args.database_type)
    install_and_setup(args.database_type)
    start_database(args.database_type)
    setup_irods(args.database_type)
    rc = run_test(args.test_name, get_irods_packages_directory())
    print("return code ", rc)
    sys.exit(rc)

if __name__ == '__main__':
    main()
