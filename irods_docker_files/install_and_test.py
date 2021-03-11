#!/usr/bin/python
from __future__ import print_function
from subprocess import Popen, PIPE

import argparse
import ci_utilities
import glob
import irods_python_ci_utilities
import os
import shutil
import subprocess
import sys
import time

def get_irods_packages_directory():
    return '/irods_build/' + irods_python_ci_utilities.get_irods_platform_string()

def get_upgrade_packages_directory():
    return '/upgrade_dir/' + irods_python_ci_utilities.get_irods_platform_string()

def get_externals_directory():
    return '/irods_externals'

def get_mungefs_directory():
    return os.path.join('/', 'opt','irods-externals','mungefs1.0.3-0','usr','bin')

def setup_irods(database_type, database_machine):
    if database_type == 'postgres':
        subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input'], shell=True)
    elif database_type == 'mysql' or database_type == 'mariadb':
        subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_mysql.input'], shell=True)
    elif database_type == 'oracle':
        status = 'running'
        while status == 'running':
            status_cmd = ['docker', 'inspect', '--format', '{{.State.Health.Status}}', database_machine]
            status_proc = Popen(status_cmd, stdout = PIPE, stderr=PIPE)
            _out, _err = status_proc.communicate()
            if 'healthy' in _out:
                status = _out

            time.sleep(1)

        subprocess.check_call(['export LD_LIBRARY_PATH=/usr/lib/oracle/11.2/client64/lib:$LD_LIBRARY_PATH; export ORACLE_HOME=/usr/lib/oracle/11.2/client64; export PATH=$ORACLE_HOME/bin:$PATH; python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_oracle.input'], shell=True)
    else:
        print(database_type, ' not supported')

def checkout_git_repo_and_run_test_hook(git_repo, git_commitish, passthrough_arguments, install_externals, database_type):
    if irods_python_ci_utilities.get_distribution() == 'Ubuntu':
        irods_python_ci_utilities.subprocess_get_output(['apt-get', 'update'], check_rc=True)
    _git_repo = git_repo.split('/')
    plugin_name = _git_repo[len(_git_repo) - 1]
    git_sha = ci_utilities.get_sha_from_commitish(git_repo, git_commitish)
    git_checkout_dir = irods_python_ci_utilities.git_clone(git_repo, git_sha)
    plugin_build_dir = '/plugin_mount_dir/{0}'.format(plugin_name)

    passthru_args = []
    if passthrough_arguments is not None:
        for args in passthrough_arguments.split(','):
            arg1 = args.split(' ')
            passthru_args = passthru_args + arg1

    if 'kerberos' in plugin_name:
        plugin_name = plugin_name.replace('kerberos', 'krb')

    if 'capability_storage_tiering' in plugin_name:
        if len(passthru_args) > 0:
            plugin_name = 'irods_rule_engine_plugin_unified_storage_tiering'
        passthru_args.extend(['--munge_path', 'export PATH={}:$PATH'.format(get_mungefs_directory())])

    plugin_basename = plugin_name.replace('_', '-') + '*'
    plugin_package = glob.glob(os.path.join(plugin_build_dir, irods_python_ci_utilities.get_irods_platform_string(), plugin_basename))

    if install_externals:
        externals_list = ci_utilities.get_package_dependencies(''.join(plugin_package))
        if len(externals_list) > 0:
            ci_utilities.install_externals_from_list(externals_list, get_externals_directory())

    python_script = 'irods_consortium_continuous_integration_test_hook.py'
    output_directory = '/irods_test_env/{0}/{1}/{2}'.format(plugin_name, irods_python_ci_utilities.get_irods_platform_string(), database_type)
    time.sleep(10)
    cmd = ['python', python_script, '--output_root_directory', output_directory, '--built_packages_root_directory', plugin_build_dir] + passthru_args
    print(cmd)
    return irods_python_ci_utilities.subprocess_get_output(cmd, cwd=git_checkout_dir, check_rc=True)

def run_test(test_name, database_type):
    try:
        test_output_file = '/var/lib/irods/log/test_output.log'

        if database_type == 'oracle':
            cmd = 'cd scripts; export PATH={0}:$PATH; python2 run_tests.py --xml_output --run_s={1} 2>&1 | tee {2}; exit $PIPESTATUS'.format(get_mungefs_directory(), test_name, test_output_file)
            rc, _, _ = irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', cmd])
        else:
            cmd = 'cd scripts; export PATH={0}:$PATH; python2 run_tests.py --use_mungefs --xml_output --run_s={1} 2>&1 | tee {2}; exit $PIPESTATUS'.format(get_mungefs_directory(), test_name, test_output_file)
            rc, _, _ = irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', cmd])
        return rc
    finally:
        output_directory = '/irods_test_env/{0}/{1}/{2}'.format(irods_python_ci_utilities.get_irods_platform_string(), database_type, test_name)
        irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_directory, lambda x: True)
        shutil.copy('/var/lib/irods/log/test_output.log', output_directory)
 
def run_unit_test(test_name):
    report_style= 'junit'
    report_filename = test_name + '_junit_report.xml'
    unit_test_binary = os.path.join(get_irods_packages_directory(), test_name)
    unit_test_cmd = "'{0}' -r {1} -o {2}".format(unit_test_binary, report_style, report_filename)
    cmd = ['su', '-', 'irods', '-c', unit_test_cmd]

    try:
        return subprocess.call(cmd)
    finally:
        src_dir = '/var/lib/irods'
        dst_dir = os.path.join('/irods_test_env', irods_python_ci_utilities.get_irods_platform_string(), 'unit_tests')
        irods_python_ci_utilities.gather_files_satisfying_predicate(src_dir, dst_dir, lambda f: os.path.basename(f).endswith('_junit_report.xml'))
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test_plugin', action='store_true', default=False)
    parser.add_argument('--upgrade_test', action='store_true', default=False)
    parser.add_argument('--install_externals', action='store_true', default=False)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--database_machine', help='database container name', default=None)
    parser.add_argument('-t', '--test_name', default=None, help='test name or the plugin name')
    parser.add_argument('--plugin_repo', default='https://github.com/irods/irods_microservice_plugins_curl.git', help='plugin repo')
    parser.add_argument('--plugin_commitish', default='4-2-stable', help='plugin commitish')
    parser.add_argument('--unit_test', action='store_true', default=False)
    parser.add_argument('--passthrough_arguments', type=str)

    args = parser.parse_args()

    ci_utilities.install_irods_packages(args.database_type, args.database_machine, args.install_externals, get_irods_packages_directory(), get_externals_directory(), is_provider=True)
    ci_utilities.setup_irods(args.database_type, 'tempZone', args.database_machine)
    ci_utilities.stop_server(ci_utilities.get_irods_version())
    ci_utilities.start_server(ci_utilities.get_irods_version())

    if args.upgrade_test:
        ci_utilities.upgrade(get_upgrade_packages_directory(), args.database_type, args.install_externals, get_externals_directory())
    
    if args.unit_test:
        sys.exit(run_unit_test(args.test_name))
    elif not args.test_plugin:    
        sys.exit(run_test(args.test_name, args.database_type))
    else:
        rc, stdout, stderr = checkout_git_repo_and_run_test_hook(args.plugin_repo, args.plugin_commitish, args.passthrough_arguments, args.install_externals, args.database_type)
        sys.exit(rc)

if __name__ == '__main__':
    main()
