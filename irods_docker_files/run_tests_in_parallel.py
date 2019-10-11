#!/usr/bin/python

from __future__ import print_function
from subprocess import Popen, PIPE
from multiprocessing import Pool
from urlparse import urlparse

import os
import sys
import argparse
import json
import requests

def download_list_of_tests(irods_repo, irods_commitish, relative_path):
    url = urlparse(irods_repo)
    tests_list_url = 'https://raw.github.com' + url.path + '/' + irods_commitish + '/' + relative_path
    response = requests.get(tests_list_url)

    print('test list url => {0}'.format(tests_list_url))
    print('response      => {0}'.format(str(response)))
    print('response text => {0}'.format(response.text))

    return json.loads(response.text)

def run_command_in_container(cmd):
    return Popen(cmd, stdout=PIPE, stderr=PIPE).wait()

def to_docker_run_commands(test_list, cmd_line_args, is_unit_test=False):
    cmd_list = []
    build_mount = cmd_line_args.build_dir + ':/irods_build'
    results_mount = cmd_line_args.jenkins_output + ':/irods_test_env'

    for test in test_list:
        container_name = cmd_line_args.test_name_prefix + '_' + test
        cmd = {'test_name': test,
               'command': ['docker', 'run', '--rm', '--init',
                                            '--name', container_name,
                                            '-v', build_mount,
                                            '-v', results_mount,
                                            cmd_line_args.image_name,
                                            '--database_type', cmd_line_args.database_type,
                                            '-t', test]}
        if is_unit_test == True:
            cmd['command'].append('--unit_test')

        cmd_list.append(cmd)

    return cmd_list

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--image_name', default='ubuntu_16:latest', help='base image name', required=True)
    parser.add_argument('-j', '--jenkins_output', default='/jenkins_output', help='jenkins output directory on the host machine', required=True)
    parser.add_argument('-t', '--test_name_prefix', help='test name prefix')
    parser.add_argument('-b', '--build_dir',  help='irods build directory', required=True)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--test_parallelism', type=str, default='4', required=True)
    args = parser.parse_args()

    # Add unit-test commands to the list.
    docker_run_list = []
    test_list = download_list_of_tests(args.irods_repo, args.irods_commitish, 'unit_tests/unit_tests_list.json')
    docker_run_list.extend(to_docker_run_commands(test_list, args, is_unit_test=True))

    # Add core-test commands to the list.
    test_list = download_list_of_tests(args.irods_repo, args.irods_commitish, 'scripts/core_tests_list.json')
    docker_run_list.extend(to_docker_run_commands(test_list, args))

    print(docker_run_list)

    pool = Pool(processes=int(args.test_parallelism))
    containers = [{'test_name': cmd['test_name'], 'proc': pool.apply_async(run_command_in_container, (cmd['command'],))} for cmd in docker_run_list]
    container_error_codes = [{'test_name': c['test_name'], 'error_code': c['proc'].get()} for c in containers]

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
