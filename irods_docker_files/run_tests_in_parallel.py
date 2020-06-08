#!/usr/bin/python

from __future__ import print_function
from subprocess import Popen, PIPE
from multiprocessing import Pool
from urlparse import urlparse
from docker_cmd_builder import DockerCommandsBuilder

import argparse
import ci_utilities
import docker_cmds_utilities
import json
import os
import requests
import subprocess
import sys

def download_list_of_tests(irods_repo, irods_sha, relative_path):
    url = urlparse(irods_repo)

    tests_list_url = 'https://raw.github.com' + url.path + '/' + irods_sha + '/' + relative_path
    response = requests.get(tests_list_url)

    print('test list url => {0}'.format(tests_list_url))
    print('response      => {0}'.format(str(response)))
    print('response text => {0}'.format(response.text))

    return json.loads(response.text)

def to_docker_commands(test_list, cmd_line_args, is_unit_test=False):
    alias_name = 'icat.example.org'
    docker_cmds_list = []
    build_mount = cmd_line_args.build_dir + ':/irods_build'
    if cmd_line_args.upgrade_packages_dir == None:
        upgrade_packages_dir = 'None'
    else:
        upgrade_packages_dir = cmd_line_args.upgrade_packages_dir
    upgrade_mount = upgrade_packages_dir + ':/upgrade_dir'
    results_mount = cmd_line_args.jenkins_output + ':/irods_test_env'
    run_mount = '/tmp/$(mktemp -d):/run'
    externals_mount = cmd_line_args.externals_dir + ':/irods_externals'
    mysql_mount = '/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz:/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz'

    for test in test_list:
        container_name = cmd_line_args.test_name_prefix + '_' + test + '_' + cmd_line_args.database_type
        database_container = None
        network_name = None
        test_type = 'standalone_icat'
        database_container = cmd_line_args.test_name_prefix + '_' + test + '_' + cmd_line_args.database_type + '-database'
        network_name = cmd_line_args.test_name_prefix + '_' + cmd_line_args.database_type + '_' + test

        if 'centos' in cmd_line_args.image_name or 'suse' in cmd_line_args.image_name:
            centosCmdBuilder = DockerCommandsBuilder()
            centosCmdBuilder.core_constructor(container_name, build_mount, upgrade_mount, results_mount, None, externals_mount, None, cmd_line_args.image_name, 'install_and_test.py', cmd_line_args.database_type, test, test_type, is_unit_test, True, database_container)
            run_cmd = centosCmdBuilder.build_run_cmd()
            exec_cmd = centosCmdBuilder.build_exec_cmd()
            stop_cmd = centosCmdBuilder.build_stop_cmd()
        elif 'ubuntu' in cmd_line_args.image_name:
            ubuntuCmdBuilder = DockerCommandsBuilder()
            ubuntuCmdBuilder.core_constructor(container_name, build_mount, upgrade_mount, results_mount, None, externals_mount, mysql_mount, cmd_line_args.image_name, 'install_and_test.py', cmd_line_args.database_type, test, test_type, is_unit_test, True, database_container)

            run_cmd = ubuntuCmdBuilder.build_run_cmd()
            exec_cmd = ubuntuCmdBuilder.build_exec_cmd()
            stop_cmd = ubuntuCmdBuilder.build_stop_cmd()
        else:
            print('OS not supported')

        extra_args = {'test_name': test, 'test_type': test_type}
        docker_cmd = docker_cmds_utilities.get_docker_cmd(run_cmd, exec_cmd, stop_cmd, container_name, alias_name, database_container, cmd_line_args.database_type, network_name, extra_args)
        docker_cmds_list.append(docker_cmd)

    return docker_cmds_list

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--image_name', default='ubuntu_16:latest', help='base image name', required=True)
    parser.add_argument('-j', '--jenkins_output', default='/jenkins_output', help='jenkins output directory on the host machine', required=True)
    parser.add_argument('-t', '--test_name_prefix', help='test name prefix')
    parser.add_argument('-b', '--build_dir',  help='irods build directory', required=True)
    parser.add_argument('--externals_dir', help='externals build directory', default=None)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--upgrade_packages_dir', required=False, default=None)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--test_parallelism', type=str, default='4', required=True)
    parser.add_argument('--is_unit_test', action='store_true', default=False)
    parser.add_argument('--run_timing_tests', action='store_true', default=False)
    args = parser.parse_args()

    # Add unit-test commands to the list.
    docker_cmds_list = []
    irods_sha = ci_utilities.get_sha_from_commitish(args.irods_repo, args.irods_commitish)

    if args.run_timing_tests:
        test_list = ['timing_tests']
    else:
        if args.is_unit_test:
            test_list = download_list_of_tests(args.irods_repo, irods_sha, 'unit_tests/unit_tests_list.json')
            docker_cmds_list.extend(to_docker_commands(test_list, args, args.is_unit_test))

        # Add core-test commands to the list.
        test_list = download_list_of_tests(args.irods_repo, irods_sha, 'scripts/core_tests_list.json')

    docker_cmds_list.extend(to_docker_commands(test_list, args))

    print(docker_cmds_list)

    run_pool = Pool(processes=int(args.test_parallelism))

    containers = [{'test_name': docker_cmd['test_name'], 'proc': run_pool.apply_async(docker_cmds_utilities.run_command_in_container, (docker_cmd['run_cmd'], docker_cmd['exec_cmd'], docker_cmd['stop_cmd'], docker_cmd['container_name'], docker_cmd['alias_name'], docker_cmd['database_container'], docker_cmd['database_type'], docker_cmd['network_name'],),{'test_type': docker_cmd['test_type'],})} for docker_cmd in docker_cmds_list]

    container_error_codes = [{'test_name': c['test_name'], 'error_code': c['proc'].get()} for c in containers]

    print(container_error_codes)

    failures = []
    for ec in container_error_codes:
        if ec['error_code'] != 0:
            failures.append(ec['test_name'])

    if len(failures) > 0:
        print('Failing Tests:')
        for test_name in failures:
            print('\t{0}'.format(test_name))
        sys.exit(1)

if __name__ == '__main__':
    main()
