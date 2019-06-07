#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
from subprocess import Popen, PIPE

def get_build_tag(base_os, stage, build_id):
    build_tag = base_os + '-' + stage + ':' + build_id
    return build_tag

def get_base_image(base_os, build_id):
    base_image = base_os + ':' + build_id
    return base_image

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def install_irods(build_tag, base_image):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} -f Dockerfile.install_and_test .'.format(build_tag, base_image)]
    run_build = subprocess.check_call(docker_cmd, shell = True)

def run_tests(image_name, build_dir, output_directory, database_type, test_name_prefix):
    run_tests_cmd = ['python run_tests_in_parallel.py --image_name {0} --jenkins_output {1} --test_name_prefix {2} -b {3} --database_type {4}'.format(image_name, output_directory, test_name_prefix, build_dir, database_type)]
    run_tests_p = subprocess.check_call(run_tests_cmd, shell=True)

def run_plugin_tests(image_name, irods_build_dir, plugin_build_dir, plugin_repo, plugin_commitish, passthru_args, output_directory, database_type, machine_name):
    build_mount = irods_build_dir + ':/irods_build'
    results_mount = output_directory + ':/irods_test_env'
    plugin_mount = plugin_build_dir + ':/plugin_mount_dir'
    run_cmd = ['docker run --rm --name {0} -v {1} -v {2} -v {3} {4} --test_plugin --database_type {5} --plugin_repo {6} --plugin_commitish {7} --passthrough_arguments {8}'.format(machine_name, build_mount, plugin_mount, results_mount, image_name, database_type, plugin_repo, plugin_commitish, passthru_args)]
    print(run_cmd)
    run_tests = subprocess.check_call(run_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--test_name_prefix', type=str, required=True)
    parser.add_argument('--irods_build_dir', type=str, required=True)
    parser.add_argument('--test_plugin', action='store_true', default=False)
    parser.add_argument('--plugin_build_dir', type=str, help='plugin build directory')
    parser.add_argument('--plugin_repo', help='plugin git repo')
    parser.add_argument('--plugin_commitish', help='plugin git commit sha')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    parser.add_argument('--passthrough_arguments', default=[], nargs=argparse.REMAINDER)
    
    args = parser.parse_args()
    build_tag = None
    base_image = get_base_image(args.platform_target, args.build_id)

    if not args.test_plugin:
        build_tag = get_build_tag(args.platform_target, 'irods-install', args.build_id)
    else:
        build_tag = get_build_tag(args.platform_target, 'plugin-install', args.build_id)
        
    install_irods(build_tag, base_image)
    test_name_prefix = args.platform_target + '-' + args.test_name_prefix
    if not args.test_plugin:
        run_tests(build_tag, args.irods_build_dir, args.output_directory, args.database_type, test_name_prefix)
    else:
        plugin_repo = args.plugin_repo
        plugin_repo_split = plugin_repo.split('/')
        plugin = plugin_repo_split[len(plugin_repo_split) - 1]
        plugin_name = plugin.split('.git')[0]
        machine_name = args.platform_target + '-' + plugin_name + '-' + args.build_id 
        run_plugin_tests(build_tag, args.irods_build_dir, args.plugin_build_dir, args.plugin_repo, args.plugin_commitish, args.passthrough_arguments, args.output_directory, args.database_type, machine_name)

if __name__ == '__main__':
    main()
