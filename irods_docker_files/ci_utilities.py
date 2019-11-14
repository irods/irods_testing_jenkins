#!/usr/bin/python
from __future__ import print_function

import os
import irods_python_ci_utilities
import subprocess

from subprocess import Popen, PIPE

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
    elif irods_python_ci_utilities.get_distribution() == 'Ubuntu':
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
    else:
        print(irods_python_ci_utilities.get_distribution(), ' distribution not supported')

    return ','.join(externals_list)

def install_externals_from_list(externals_list, externals_dir):
    install_externals_cmd = 'python install_externals.py --externals_root_directory {0} --externals_to_install {1}'.format(externals_dir, externals_list)
    subprocess.check_call(install_externals_cmd, shell=True)

def install_irods_repository_apt():
    irods_python_ci_utilities.subprocess_get_output('wget -qO - https://core-dev.irods.org/irods-core-dev-signing-key.asc | sudo apt-key add -', shell=True, check_rc=True)
    irods_python_ci_utilities.subprocess_get_output('echo "deb [arch=amd64] https://core-dev.irods.org/apt/ $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/renci-irods-core-dev.list', shell=True, check_rc=True)
    subprocess.check_call('apt-get clean && apt-get update', shell=True)

def install_irods_repository_yum():
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'rpm', '--import', 'https://core-dev.irods.org/irods-core-dev-signing-key.asc'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output('wget -qO - https://core-dev.irods.org/renci-irods-core-dev.yum.repo | sudo tee /etc/yum.repos.d/renci-irods-core-dev.yum.repo', shell=True, check_rc=True)

def install_irods_repository_zypper():
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'rpm', '--import', 'https://core-dev.irods.org/irods-core-dev-signing-key.asc'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output('wget -qO - https://core-dev.irods.org/renci-irods-core-dev.zypp.repo | sudo tee /etc/zypp/repos.d/renci-irods-core-dev.zypp.repo', shell=True, check_rc=True)

def install_irods_repository():
    dispatch_map = {
        'Ubuntu': install_irods_repository_apt,
        'Centos': install_irods_repository_yum,
        'Centos linux': install_irods_repository_yum,
        'Opensuse ': install_irods_repository_zypper,
    }

    try:
        return dispatch_map[irods_python_ci_utilities.get_distribution()]()
    except KeyError:
        irods_python_ci_utilities.raise_not_implemented_for_distribution()

def get_munge_external():
    munge_external = 'irods-externals-mungefs*'
    return munge_external

def install_irods_packages(database_type, install_externals, irods_packages_directory, externals_directory):
    install_database = 'python install_database.py --database_type {0}'.format(database_type)
    subprocess.check_call(install_database, shell=True)

    if irods_python_ci_utilities.get_distribution() == 'Centos linux':
        irods_python_ci_utilities.subprocess_get_output(['rpm', '--rebuilddb'], check_rc=True)

    if os.path.exists(irods_packages_directory):
        icat_package_basename = filter(lambda x:'irods-server' in x, os.listdir(irods_packages_directory))[0]
        if 'irods-server' in icat_package_basename:
            server_package = os.path.join(irods_packages_directory, icat_package_basename)
            if install_externals:
                externals_list = get_package_dependencies(server_package)
                externals_list = externals_list + ',' + get_munge_external()
                install_externals_from_list(externals_list, externals_directory)
            else:
                install_irods_repository()
                #need to install munge here too after munge in core dev

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

