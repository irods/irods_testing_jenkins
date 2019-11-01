#!/usr/bin/python

from __future__ import print_function
from subprocess import Popen, PIPE
from multiprocessing import Pool
from urlparse import urlparse
from docker_cmd_builder import DockerCommandsBuilder

import os
import sys
import time
import argparse
import json
import subprocess
import requests

def download_list_of_tests(irods_repo, irods_commitish, relative_path):
    url = urlparse(irods_repo)
    tests_list_url = 'https://raw.github.com' + url.path + '/' + irods_commitish + '/' + relative_path
    response = requests.get(tests_list_url)

    print('test list url => {0}'.format(tests_list_url))
    print('response      => {0}'.format(str(response)))
    print('response text => {0}'.format(response.text))

    return json.loads(response.text)

def run_command_in_container(run_cmd, exec_cmd, stop_cmd, container_name):
    # the docker run command (stand up a container)
    run_proc = Popen(run_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = run_proc.communicate()
    _running = False
    state_cmd = ['docker', 'inspect', '-f', '{{.State.Running}}', container_name]
    while not _running:
        state_proc = Popen(state_cmd, stdout=PIPE, stderr=PIPE)
        _sout, _serr = state_proc.communicate()
        if 'true' in _sout:
            _running = True
        time.sleep(1)

    _rrc = run_proc.returncode
    # execute a command in the running container
    exec_proc = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _eout, _eerr = exec_proc.communicate()
    _rc = exec_proc.returncode
    # stop the container
    stop_proc = Popen(stop_cmd, stdout=PIPE, stderr=PIPE)
    return _rc

def get_docker_cmd(test, run_cmd, exec_cmd, stop_cmd, container_name):
    docker_cmd = {'test_name': test,
                  'run_cmd': run_cmd,
                  'exec_cmd': exec_cmd,
                  'stop_cmd': stop_cmd,
                  'container_name': container_name
                 }
    return docker_cmd

def to_docker_commands(test_list, cmd_line_args, is_unit_test=False):
    docker_cmds_list = []
    build_mount = cmd_line_args.build_dir + ':/irods_build'
    results_mount = cmd_line_args.jenkins_output + '/' + cmd_line_args.database_type + ':/irods_test_env'
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
    run_mount = '/tmp/$(mktemp -d):/run'
    externals_mount = cmd_line_args.externals_dir + ':/irods_externals'
    mysql_mount = '/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz:/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz'

    for test in test_list:
        container_name = cmd_line_args.test_name_prefix + '_' + cmd_line_args.database_type + '_' + test
        if 'centos' in cmd_line_args.image_name:
            centosCmdBuilder = DockerCommandsBuilder()
            centosCmdBuilder.core_constructor(container_name, build_mount, results_mount, cgroup_mount, None, externals_mount, None, cmd_line_args.image_name, 'install_and_test.py', cmd_line_args.database_type, test, is_unit_test)
            run_cmd = centosCmdBuilder.build_run_cmd()
            exec_cmd = centosCmdBuilder.build_exec_cmd()
            stop_cmd = centosCmdBuilder.build_stop_cmd()
            docker_cmd = get_docker_cmd(test, run_cmd, exec_cmd, stop_cmd, container_name)
        elif 'ubuntu' in cmd_line_args.image_name:
            ubuntuCmdBuilder = DockerCommandsBuilder()
            ubuntuCmdBuilder.core_constructor(container_name, build_mount, results_mount, cgroup_mount, None, externals_mount, mysql_mount, cmd_line_args.image_name, 'install_and_test.py', cmd_line_args.database_type, test, is_unit_test)

            run_cmd = ubuntuCmdBuilder.build_run_cmd()
            exec_cmd = ubuntuCmdBuilder.build_exec_cmd()
            stop_cmd = ubuntuCmdBuilder.build_stop_cmd()
            docker_cmd = get_docker_cmd(test, run_cmd, exec_cmd, stop_cmd, container_name)
        else:
            print('OS not supported')

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
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--test_parallelism', type=str, default='4', required=True)
    args = parser.parse_args()

    # Add unit-test commands to the list.
    docker_cmds_list = []
    test_list = download_list_of_tests(args.irods_repo, args.irods_commitish, 'unit_tests/unit_tests_list.json')
    docker_cmds_list.extend(to_docker_commands(test_list, args, is_unit_test=True))

    # Add core-test commands to the list.
    test_list = download_list_of_tests(args.irods_repo, args.irods_commitish, 'scripts/core_tests_list.json')

    docker_cmds_list.extend(to_docker_commands(test_list, args))

    print(docker_cmds_list)

    run_pool = Pool(processes=int(args.test_parallelism))

    containers = [{'test_name': docker_cmd['test_name'], 'proc': run_pool.apply_async(run_command_in_container, (docker_cmd['run_cmd'], docker_cmd['exec_cmd'], docker_cmd['stop_cmd'], docker_cmd['container_name']))} for docker_cmd in docker_cmds_list]

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
