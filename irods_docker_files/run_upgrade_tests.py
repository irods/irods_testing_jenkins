#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import sys
import ci_utilities

from subprocess import Popen, PIPE
from docker_cmd_builder import DockerCommandsBuilder

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def install_irods(build_tag, base_image, database_type):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} -f Dockerfile.install_and_test .'.format(build_tag, base_image)]
    run_build = subprocess.check_call(docker_cmd, shell = True)
    if database_type == 'oracle':
        docker_cmd = ['docker build -t {0} -f Dockerfile.xe .'.format('oracle/database:11.2.0.2-xe')]
        run_build = subprocess.check_call(docker_cmd, shell = True)

def run_tests(image_name, irods_repo, irods_commitish, build_dir, upgrade_packages_dir, output_directory, database_type, test_parallelism, test_name_prefix, externals_dir):
    run_tests_cmd = ['python run_tests_in_parallel.py --image_name {0} --jenkins_output {1} --test_name_prefix {2} -b {3} --database_type {4} --irods_repo {5} --irods_commitish {6} --test_parallelism {7} --externals_dir {8} --upgrade_packages_dir {9}'.format(image_name, output_directory, test_name_prefix, build_dir, database_type, irods_repo, irods_commitish, test_parallelism, externals_dir, upgrade_packages_dir)]
    run_tests_p = subprocess.check_call(run_tests_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--test_name_prefix', type=str, required=True)
    parser.add_argument('--irods_build_dir', type=str, required=True)
    parser.add_argument('--upgrade_packages_dir', type=str, required=True)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--externals_dir', type=str, help='externals build directory')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--test_parallelism', default='4', help='The number of tests to run in parallel', required=False)
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    
    args = parser.parse_args()
    build_tag = None
    base_image = ci_utilities.get_base_image(args.platform_target, args.build_id)

    build_tag = ci_utilities.get_build_tag(args.platform_target, 'irods-install-upgrade', args.build_id)
    
    install_irods(build_tag, base_image, args.database_type)
    test_name_prefix = args.platform_target + '-' + args.test_name_prefix

    print(args.externals_dir)
    run_tests(build_tag, args.irods_repo, args.irods_commitish, args.irods_build_dir, args.upgrade_packages_dir, args.output_directory, args.database_type, args.test_parallelism, test_name_prefix, args.externals_dir)

if __name__ == '__main__':
    main()
