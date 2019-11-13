#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import sys
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

def get_package_dependencies(package_name):
    externals_list = []
    if irods_python_ci_utilities.get_distribution() == 'Centos linux':
        proc = Popen(['rpm', '-qp', package_name, '--requires', '|', 'grep', 'irods-externals'], stdout=PIPE, stderr=PIPE)
        _out, _err = proc.communicate()
        _out_list = _out.split('\n')
        for _str in _out_list:
            if 'irods-externals' in _str:
                _str = _str.strip() + '*'
                externals_list.append(_str)
    else:
        proc = Popen(['dpkg', '-I', package_name], stdout=PIPE, stderr=PIPE)
        _out, _err = proc.communicate()
        _out_list = _out.split('\n')
        for _str in _out_list:
            if 'irods-externals' in _str:
                dependency_list = _str.split(':')[1].split(',')
                for dependency in dependency_list:
                    if 'irods-externals' in dependency:
                        dependency = dependency.strip() + '*'
                        externals_list.append(dependency)

    return ','.join(externals_list)

def get_munge_external():
    munge_external = 'irods-externals-mungefs*'
    return munge_external

def install_externals_from_list(externals_list):
    install_externals_cmd = 'python install_externals.py --externals_root_directory {0} --externals_to_install {1}'.format(get_externals_directory(), externals_list)
    subprocess.check_call(install_externals_cmd, shell=True)

def setup_irods(database_type, database_machine):
    if database_type == 'postgres':
        subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input'], shell=True)
    elif database_type == 'mysql':
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

def checkout_git_repo_and_run_test_hook(git_repo, git_commitish, passthrough_arguments, install_externals):
    if irods_python_ci_utilities.get_distribution() == 'Ubuntu':
        irods_python_ci_utilities.subprocess_get_output(['apt-get', 'update'], check_rc=True)
    _git_repo = git_repo.split('/')
    plugin_name = _git_repo[len(_git_repo) - 1]
    git_checkout_dir = irods_python_ci_utilities.git_clone(git_repo, git_commitish)
    output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(), plugin_name)
    plugin_build_dir = '/plugin_mount_dir/{0}'.format(plugin_name)
    if install_externals:
        plugin_basename = plugin_name + '*'
        plugin_package = os.path.join(plugin_build_dir, plugin_basename)
        externals_list = get_package_dependencies(plugin_package)
        install_externals_from_list(externals_list)

    python_script = 'irods_consortium_continuous_integration_test_hook.py'
    passthru_args = []
    if passthrough_arguments is not None:
        for args in passthrough_arguments.split(','):
            arg1 = args.split(' ')
            passthru_args = passthru_args + arg1

    if 'irods_capability_storage_tiering' in plugin_name:
        passthru_args.extend(['--munge_path', 'export PATH=/opt/irods-externals/mungefs1.0.1-0/usr/bin:$PATH'])

    cmd = ['python', python_script, '--output_root_directory', output_directory, '--built_packages_root_directory', plugin_build_dir] + passthru_args
    print(cmd)
    return irods_python_ci_utilities.subprocess_get_output(cmd, cwd=git_checkout_dir, check_rc=True)

def run_test(test_name, output_root_directory):
    try:
        test_output_file = '/var/lib/irods/log/test_output.log'
        rc, stdout, stderr = irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'cd scripts; export PATH=/opt/irods-externals/mungefs1.0.1-0/usr/bin:$PATH; python2 run_tests.py --use_mungefs --xml_output --run_s={0} 2>&1 | tee {1}; exit $PIPESTATUS'.format(test_name, test_output_file)])
        return rc
    finally:
        output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(),test_name)
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
    parser.add_argument('--install_externals', action='store_true', default=False)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--database_machine', help='oracle database container name', default=None)
    parser.add_argument('-t', '--test_name', default=None, help='test name or the plugin name')
    parser.add_argument('--plugin_repo', default='https://github.com/irods/irods_microservice_plugins_curl.git', help='plugin repo')
    parser.add_argument('--plugin_commitish', default='4-2-stable', help='plugin commitish')
    parser.add_argument('--unit_test', action='store_true', default=False)
    parser.add_argument('--passthrough_arguments', type=str)

    args = parser.parse_args()

    ci_utilities.install_irods_packages(args.database_type, args.install_externals, get_irods_packages_directory())

    setup_irods(args.database_type, args.database_machine)

    if args.unit_test:
        sys.exit(run_unit_test(args.test_name))
    elif not args.test_plugin:    
        rc = run_test(args.test_name, get_irods_packages_directory())
        sys.exit(rc)
    else:
        rc, stdout, stderr = checkout_git_repo_and_run_test_hook(args.plugin_repo, args.plugin_commitish, args.passthrough_arguments, args.install_externals)
        sys.exit(rc)

if __name__ == '__main__':
    main()
