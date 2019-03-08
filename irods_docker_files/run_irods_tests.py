#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
from subprocess import Popen, PIPE

def install_irods(base_os, build_id, prefix, build_dir, output_directory):
    build_tag = base_os +  '-irods-install:' + build_id
    base_image = base_os + ':' + build_id
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} -f Dockerfile.install_and_test .'.format(build_tag, base_image)]
    run_build = subprocess.check_call(docker_cmd, shell = True)
    test_name_prefix = base_os + '-' + prefix
    #run_tests('ub16_test:1', output_directory, 'jas_test')
    run_tests(build_tag, build_dir, output_directory, test_name_prefix)

def run_tests(image_name, build_dir, output_directory, test_name_prefix):
    run_tests_cmd = ['python run_tests_in_parallel.py --image_name {0} --jenkins_output {1} --test_name_prefix {2} -b {3} --database_type postgres'.format(image_name, output_directory, test_name_prefix, build_dir)]
    run_tests_p = subprocess.check_call(run_tests_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--test_name_prefix', type=str, required=True)
    parser.add_argument('--build_dir', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    
    args = parser.parse_args()
    install_irods(args.platform_target, args.build_id, args.test_name_prefix, args.build_dir, args.output_directory)    

if __name__ == '__main__':
    main()

