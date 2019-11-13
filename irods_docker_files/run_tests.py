#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import sys
from subprocess import Popen, PIPE
from docker_cmd_builder import DockerCommandsBuilder

def get_build_tag(base_os, stage, build_id):
    build_tag = base_os + '-' + stage + ':' + build_id
    return build_tag

def get_base_image(base_os, build_id):
    base_image = base_os + ':' + build_id
    return base_image

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def install_irods(build_tag, base_image, database_type):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} -f Dockerfile.install_and_test .'.format(build_tag, base_image)]
    run_build = subprocess.check_call(docker_cmd, shell = True)
    if database_type == 'oracle':
        docker_cmd = ['docker build -t {0} -f Dockerfile.xe .'.format('oracle/database:11.2.0.2-xe')]
        run_build = subprocess.check_call(docker_cmd, shell = True)

def run_tests(image_name, irods_repo, irods_commitish, build_dir, output_directory, database_type, test_parallelism, test_name_prefix, externals_dir):
    run_tests_cmd = ['python run_tests_in_parallel.py --image_name {0} --jenkins_output {1} --test_name_prefix {2} -b {3} --database_type {4} --irods_repo {5} --irods_commitish {6} --test_parallelism {7} --externals_dir {8}'.format(image_name, output_directory, test_name_prefix, build_dir, database_type, irods_repo, irods_commitish, test_parallelism, externals_dir)]
    run_tests_p = subprocess.check_call(run_tests_cmd, shell=True)

def run_plugin_tests(image_name, irods_build_dir, plugin_build_dir, plugin_repo, plugin_commitish, passthru_args, output_directory, database_type, machine_name, externals_dir):
    build_mount = irods_build_dir + ':/irods_build'
    results_mount = output_directory + ':/irods_test_env'
    plugin_mount = plugin_build_dir + ':/plugin_mount_dir'
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
    run_mount = '/tmp/$(mktemp -d):/run'
    externals_mount = externals_dir + ':/irods_externals'
    key_mount = '/projects/irods/vsphere-testing/externals/amazon_web_services-CI.keypair:/projects/irods/vsphere-testing/externals/amazon_web_services-CI.keypair'

    if 'centos' in machine_name:
        centosCmdBuilder = DockerCommandsBuilder()
        centosCmdBuilder.plugin_constructor(machine_name, build_mount, plugin_mount, results_mount, cgroup_mount, key_mount, run_mount, externals_mount, image_name, 'install_and_test.py', database_type, plugin_repo, plugin_commitish, passthru_args)
        
        run_cmd = centosCmdBuilder.build_run_cmd()
        exec_cmd = centosCmdBuilder.build_exec_cmd()
        stop_cmd = centosCmdBuilder.build_stop_cmd()
    elif 'ubuntu' in machine_name:
        ubuntuCmdBuilder = DockerCommandsBuilder()
        ubuntuCmdBuilder.plugin_constructor(machine_name, build_mount, plugin_mount, results_mount, cgroup_mount, key_mount, None, externals_mount, image_name, 'install_and_test.py', database_type, plugin_repo, plugin_commitish, passthru_args)
        
        run_cmd = ubuntuCmdBuilder.build_run_cmd()
        exec_cmd = ubuntuCmdBuilder.build_exec_cmd()
        stop_cmd = ubuntuCmdBuilder.build_stop_cmd()
    else:
        print('OS not supported')

    run_image = Popen(run_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = run_image.communicate()
    exec_tests = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _eout, _eerr = exec_tests.communicate()
    _rc = exec_tests.returncode
    stop_container = Popen(stop_cmd, stdout=PIPE, stderr=PIPE)
    print('return code --->>> ', _rc)
    sys.exit(_rc)

def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_repo', type=str, required=False)
    parser.add_argument('--irods_commitish', type=str, required=False)
    parser.add_argument('--test_name_prefix', type=str, required=True)
    parser.add_argument('--irods_build_dir', type=str, required=True)
    parser.add_argument('--test_plugin', action='store_true', default=False)
    parser.add_argument('--externals_dir', type=str, help='externals build directory')
    parser.add_argument('--plugin_build_dir', type=str, help='plugin build directory')
    parser.add_argument('--plugin_repo', help='plugin git repo')
    parser.add_argument('--plugin_commitish', help='plugin git commit sha')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--test_parallelism', default='4', help='The number of tests to run in parallel', required=False)
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    parser.add_argument('--passthrough_arguments', type=str)
    
    args = parser.parse_args()
    build_tag = None
    base_image = get_base_image(args.platform_target, args.build_id)

    if not args.test_plugin:
        build_tag = get_build_tag(args.platform_target, 'irods-install', args.build_id)
    else:
        build_tag = get_build_tag(args.platform_target, 'plugin-install', args.build_id)
    
    install_irods(build_tag, base_image, args.database_type)
    test_name_prefix = args.platform_target + '-' + args.test_name_prefix

    if not args.test_plugin:
        print(args.externals_dir)
        run_tests(build_tag, args.irods_repo, args.irods_commitish, args.irods_build_dir, args.output_directory, args.database_type, args.test_parallelism, test_name_prefix, args.externals_dir)
    else:
        plugin_repo = args.plugin_repo
        plugin_repo_split = plugin_repo.split('/')
        plugin = plugin_repo_split[len(plugin_repo_split) - 1]
        plugin_name = plugin.split('.git')[0]
        if 'audit' in plugin_name:
            if '--message_broker' in args.passthrough_arguments:
                message_broker = args.passthrough_arguments.split(' ')[1]
                machine_name = args.platform_target + '-' + plugin_name + '-' + message_broker + '-' + args.build_id
        else:
            machine_name = args.platform_target + '-' + plugin_name + '-' + args.build_id

        run_plugin_tests(build_tag, args.irods_build_dir, args.plugin_build_dir, args.plugin_repo, args.plugin_commitish, args.passthrough_arguments, args.output_directory, args.database_type, machine_name, args.externals_dir)

if __name__ == '__main__':
    main()
