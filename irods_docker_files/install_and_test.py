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

def checkout_git_repo_and_run_test_hook(git_repo, git_commitish, passthrough_arguments):
    if irods_python_ci_utilities.get_distribution() == 'Ubuntu':
        irods_python_ci_utilities.subprocess_get_output(['apt-get', 'update'], check_rc=True)
    _git_repo = git_repo.split('/')
    plugin_name = _git_repo[len(_git_repo) - 1]
    git_checkout_dir = irods_python_ci_utilities.git_clone(git_repo, git_commitish)
    output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(), plugin_name)
    plugin_build_dir = '/plugin_mount_dir/{0}'.format(plugin_name)
    python_script = 'irods_consortium_continuous_integration_test_hook.py'
    return irods_python_ci_utilities.subprocess_get_output(['python', python_script, '--output_root_directory', output_directory, '--built_packages_root_directory', plugin_build_dir] + passthrough_arguments, cwd=git_checkout_dir, check_rc=True)

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
    parser.add_argument('--test_plugin', action='store_true', default=False)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-t', '--test_name', default=None, help='test name or the plugin name')
    parser.add_argument('--plugin_repo', default='https://github.com/irods/irods_microservice_plugins_curl.git', help='plugin repo')
    parser.add_argument('--plugin_commitish', default='4-2-stable', help='plugin commitish')
    parser.add_argument('--passthrough_arguments', default=[], nargs=argparse.REMAINDER)

    args = parser.parse_args()
    install_and_setup(args.database_type)
    start_database(args.database_type)
    setup_irods(args.database_type)
    test_name = args.test_name
    
    if not args.test_plugin:    
        rc = run_test(args.test_name, get_irods_packages_directory())
        sys.exit(rc)
    else:
        rc, stdout, stderr = checkout_git_repo_and_run_test_hook(args.plugin_repo, args.plugin_commitish, args.passthrough_arguments)
        sys.exit(rc)
        

if __name__ == '__main__':
    main()
