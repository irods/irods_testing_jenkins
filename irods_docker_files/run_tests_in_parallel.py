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

def download_list_of_core_tests(irods_repo, irods_commitish):
    url = urlparse(irods_repo)
    core_tests_list_url = 'https://raw.github.com' + url.path + '/' + irods_commitish + '/scripts/core_tests_list.json'
    response = requests.get(core_tests_list_url)

    print('core tests list url => {0}'.format(core_tests_list_url))
    print('response            => {0}'.format(str(response)))
    print('response text       => {0}'.format(response.text))

    return json.loads(response.text)

def run_command_in_container(cmd):
    return Popen(cmd, stdout=PIPE, stderr=PIPE).wait()

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

    build_mount = args.build_dir + ':/irods_build'
    results_mount = args.jenkins_output + ':/irods_test_env'

    test_list = download_list_of_core_tests(args.irods_repo, args.irods_commitish)
    test_list.sort()

    docker_run_list = []
    for test in test_list:
        test_name = args.test_name_prefix + '_' + test
        cmd = {'test_name': test,
               'command': ['docker', 'run', '--rm', '--init',
                                            '--name', test_name,
                                            '-v', build_mount,
                                            '-v', results_mount,
                                            args.image_name,
                                            '--database_type', args.database_type,
                                            '-t', test]}
        docker_run_list.append(cmd)
    
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
