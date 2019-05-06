#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import json
import sys
from subprocess import Popen, PIPE

def get_build_tag(base_os, stage, build_id):
    build_tag = base_os + '-' + stage + ':' + build_id
    return build_tag

def get_network_name(base_os, build_id):
    network_name = base_os + '_topo_net_' + build_id
    return network_name

def get_base_image(base_os, build_id):
    base_image = base_os + ':' + build_id
    return base_image

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def install_irods(build_tag, base_image, install_database):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} --build-arg arg_install_database={2} -f Dockerfile.topo .'.format(build_tag, base_image, install_database)]
    run_build = subprocess.check_call(docker_cmd, shell = True)

def build_topo_containers(platform_target, build_id, irods_build_dir, test_name_prefix, output_directory, database_type, providers, consumers, test_type, test_name):
    base_image = get_base_image(platform_target, build_id)
    provider_tag = get_build_tag(platform_target, 'topo_provider', build_id)
    install_irods(provider_tag, base_image, 'True')
    consumer_tag_list=[]
    for x in range(consumers):
        consumer_id = x + 1
        stage = 'topo_consumer_' + str(consumer_id)
        consumer_tag = get_build_tag(platform_target, stage, build_id)
        install_irods(consumer_tag, base_image, 'False')
        consumer_tag_list.append(consumer_tag)

    network_name = get_network_name(platform_target, build_id)

    create_topo_network(network_name)
    create_topology(provider_tag, consumer_tag_list, network_name, test_name_prefix, output_directory, database_type, irods_build_dir, platform_target, test_type, test_name)

def create_topo_network(network_name):
    docker_cmd = ['docker', 'network', 'create', '--attachable', network_name]
    network = subprocess.check_call(docker_cmd)

def create_topology(provider_tag, consumer_tag_list, network_name, test_name_prefix, output_directory, database_type, irods_build_dir, platform_target, test_type, test_name):
    docker_run_list = []
    machine_list = []
    docker_socket = '/var/run/docker.sock:/var/run/docker.sock'
    build_mount = irods_build_dir + ':/irods_build'
    results_mount = output_directory + ':/irods_test_env' 
    provider_name = platform_target + '-' + test_name_prefix + '-provider'
    consumer_name = platform_target + '-' + test_name_prefix + '-consumer-1'
    print(network_name)
    machine_list.append(provider_name)
    
    if test_type == 'topology_icat':
        provider_cmd = ['docker', 'run', '--name', provider_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '--expose', '1248', '--expose', '1247', '-h', 'icat.example.org', '-P', provider_tag, '--database_type', database_type, '--provider_name', provider_name, '--test_type', test_type, '--test_name', test_name, '--network_name', network_name, '--alias_name', 'icat.example.org']
    else:
        provider_cmd = ['docker', 'run', '--name', provider_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '--expose', '1248', '--expose', '1247', '-h', 'icat.example.org','-P', provider_tag, '--database_type', database_type, '--provider_name', provider_name,  '--network_name', network_name, '--alias_name', 'icat.example.org', '--consumer_name', consumer_name]

    print(provider_cmd)

    docker_run_list.append(provider_cmd)
    for i, consumer_tag in enumerate(consumer_tag_list, start=1):
        consumer_name = platform_target + '-' + test_name_prefix + '-consumer-' + str(i)
        machine_list.append(consumer_name)
        resource_name = 'resource' + str(i) + '.example.org'
        if test_type == 'topology_resource' and i == 1:
            consumer_cmd = ['docker', 'run', '--name', consumer_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-h', resource_name, consumer_tag, '--database_type', database_type, '--is_consumer', '--consumer_name', consumer_name, '--provider_name', provider_name, '--test_type', test_type, '--test_name', test_name, '--network_name', network_name, '--alias_name', resource_name]
        else:
            consumer_cmd = ['docker', 'run', '--name', consumer_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-h', resource_name, consumer_tag, '--database_type', database_type, '--is_consumer', '--consumer_name', consumer_name, '--provider_name', provider_name, '--network_name', network_name, '--alias_name', resource_name]

        docker_run_list.append(consumer_cmd)
        print(consumer_cmd)

    topo_procs = [Popen(docker_cmd, stdout=PIPE, stderr=PIPE) for docker_cmd in docker_run_list]
    exit_codes = [proc.wait() for proc in topo_procs]
    check_topo_state(machine_list, network_name)

def check_topo_state(machine_list, network_name):
    exit_codes = []
    for machine_name in machine_list:
        is_running = True
        while is_running:
            cmd = ['docker', 'inspect', '--format', '{{.State.Running}}', machine_name]
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            output, err = proc.communicate()
            if 'false' in output:
                is_running = False
                exit_code = ['docker', 'inspect', '--format', '{{.State.ExitCode}}', machine_name]
                ec_proc = Popen(exit_code, stdout=PIPE, stderr=PIPE)
                _out, _err = ec_proc.communicate()
                p = Popen(['docker', 'rm', machine_name], stdout=PIPE, stderr=PIPE)
                p.wait()
                if not _out == "0\n":
                    exit_codes.append(_out)
    
    rm_network = Popen(['docker', 'network', 'rm', network_name], stdout=PIPE, stderr=PIPE)
    rm_network.wait()
    if len(exit_codes) > 0:
        sys.exit(1)

    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_build_dir', type=str, required=True)
    parser.add_argument('--test_name_prefix', type=str)
    parser.add_argument('--test_type', type=str, required=False, choices=['standalone_icat', 'topology_icat', 'topology_resource', 'federation'])
    parser.add_argument('--specific_test', type=str)
    parser.add_argument('--consumers', type=int, default=3, help='number of consumers')
    parser.add_argument('--providers', type=int, default=1, help='number of providers')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=False)
    
    args = parser.parse_args()

    print('specific_test ', args.specific_test)
    print('test_type ' , args.test_type)

    build_topo_containers(args.platform_target, args.build_id, args.irods_build_dir, args.test_name_prefix, args.output_directory, args.database_type, args.providers, args.consumers, args.test_type, args.specific_test)

        
if __name__ == '__main__':
    main()

