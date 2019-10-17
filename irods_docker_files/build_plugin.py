#!/usr/bin/python

from __future__ import print_function

import argparse
import os
import subprocess
import irods_python_ci_utilities
from subprocess import Popen, PIPE

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

def build_plugin(irods_build_directory, output_directory):
    build_hook = '/irods_plugin/irods_consortium_continuous_integration_build_hook.py'
    if os.path.exists(build_hook):
        build_cmd = ['python {0} --irods_packages_root_directory {1} --output_root_directory {2}'.format(build_hook, irods_build_directory, output_directory)]
        build_p = subprocess.check_call(build_cmd, shell=True)
    

def main():
    parser = argparse.ArgumentParser(description='build plugins in os-containers')
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    parser.add_argument('-b', '--irods_build_directory', type=str, required=True)

    args = parser.parse_args()
    install_irods_repository()
    build_plugin(args.irods_build_directory, args.output_directory)

if __name__ == '__main__':
    main()
