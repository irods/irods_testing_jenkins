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

def run_tests(image_name, irods_repo, irods_sha, build_dir, upgrade_packages_dir, output_directory, database_type, test_parallelism, test_name_prefix, externals_dir):
    run_tests_cmd = ['python run_tests_in_parallel.py --image_name {image_name} --jenkins_output {output_directory} --test_name_prefix {test_name_prefix} -b {build_dir} --database_type {database_type} --irods_repo {irods_repo} --irods_commitish {irods_sha} --test_parallelism {test_parallelism} --externals_dir {externals_dir} --upgrade_packages_dir {upgrade_packages_dir}'.format(**locals())]
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
    irods_sha = ci_utilities.get_sha_from_commitish(args.irods_repo, args.irods_commitish)
    run_tests(build_tag, args.irods_repo, irods_sha, args.irods_build_dir, args.upgrade_packages_dir, args.output_directory, args.database_type, args.test_parallelism, test_name_prefix, args.externals_dir)

if __name__ == '__main__':
    main()
