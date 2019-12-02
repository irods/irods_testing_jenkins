#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import json
import sys
import time
import ci_utilities

from subprocess import Popen, PIPE
from multiprocessing import Pool

def get_network_name(base_os, build_id):
    network_name = base_os + '_topo_net_' + build_id
    return network_name

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def get_docker_cmd(resource, test_type, exec_cmd, stop_cmd, container_name):
    docker_cmd = {'resource_type': resource,
                  'test_type': test_type,
                  'exec_cmd': exec_cmd,
                  'stop_cmd': stop_cmd,
                  'container_name': container_name
                 }
    return docker_cmd

def run_command_in_container(exec_cmd, stop_cmd, container_name):
    _running = False
    state_cmd = ['docker', 'inspect', '-f', '{{.State.Running}}', container_name]
    while not _running:
        state_proc = Popen(state_cmd, stdout=PIPE, stderr=PIPE)
        _sout, _serr = state_proc.communicate()
        if 'true' in _sout:
            _running = True
        time.sleep(1)
    
    exec_proc = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = exec_proc.communicate()
    _rc = exec_proc.returncode
    if _rc != 0:
        print('output from exec_proc...')
        print('stdout:[' + str(_out) + ']')
        print('stderr:[' + str(_err) + ']')
        print('return code:[' + str(_rc) + ']')
    stop_proc = Popen(stop_cmd, stdout=PIPE, stderr=PIPE)
    return _rc

def install_irods(build_tag, base_image, install_database):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} --build-arg arg_install_database={2} -f Dockerfile.topo .'.format(build_tag, base_image, install_database)]
    run_build = subprocess.check_call(docker_cmd, shell = True)

def build_topo_containers(platform_target, build_id, irods_build_dir, test_name_prefix, output_directory, database_type, providers, consumers, test_type, test_name):
    base_image = ci_utilities.get_base_image(platform_target, build_id)
    provider_tag = ci_utilities.get_build_tag(platform_target, 'topo_provider', build_id)
    install_irods(provider_tag, base_image, 'True')
    consumer_tag_list=[]
    for x in range(consumers):
        consumer_id = x + 1
        stage = 'topo_consumer_' + str(consumer_id)
        consumer_tag = ci_utilities.get_build_tag(platform_target, stage, build_id)
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
    docker_cmds_list = []
    machine_list = []
    docker_socket = '/var/run/docker.sock:/var/run/docker.sock'
    build_mount = irods_build_dir + ':/irods_build'
    results_mount = output_directory + ':/irods_test_env'
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
    provider_name = platform_target + '-' + test_name_prefix + '-provider'
    consumer_name = platform_target + '-' + test_name_prefix + '-consumer-1'
    print(network_name)
    machine_list.append(provider_name)
    
    if test_type == 'topology_icat':
        provider_run_cmd = ['docker', 'run', '-d', '--rm', '--name', provider_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-v', cgroup_mount, '--expose', '1248', '--expose', '1247', '-h', 'icat.example.org', '-P', provider_tag]
        provider_exec_cmd = ['docker', 'exec', provider_name, 'python', 'setup_topo.py', '--database_type', database_type, '--provider_name', provider_name, '--test_type', test_type, '--test_name', test_name, '--network_name', network_name, '--alias_name', 'icat.example.org']
    else:
        provider_run_cmd = ['docker', 'run', '-d', '--rm', '--name', provider_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-v', cgroup_mount, '--expose', '1248', '--expose', '1247', '-h', 'icat.example.org','-P', provider_tag]
        provider_exec_cmd = ['docker', 'exec', provider_name, 'python', 'setup_topo.py', '--database_type', database_type, '--provider_name', provider_name,  '--network_name', network_name, '--alias_name', 'icat.example.org', '--consumer_name', consumer_name]
    
    print(provider_exec_cmd)
    provider_stop_cmd = ['docker', 'stop', provider_name]
    docker_cmd = get_docker_cmd('provider', test_type, provider_exec_cmd, provider_stop_cmd, provider_name)
    docker_run_list.append(provider_run_cmd)
    docker_cmds_list.append(docker_cmd)
    
    for i, consumer_tag in enumerate(consumer_tag_list, start=1):
        consumer_name = platform_target + '-' + test_name_prefix + '-consumer-' + str(i)
        machine_list.append(consumer_name)
        resource_name = 'resource' + str(i) + '.example.org'
        if test_type == 'topology_resource' and i == 1:
            consumer_run_cmd = ['docker', 'run', '-d', '--rm', '--name', consumer_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-v', cgroup_mount, '-h', resource_name, consumer_tag]
            consumer_exec_cmd = ['docker', 'exec', consumer_name,'python', 'setup_topo.py', '--database_type', database_type, '--is_consumer', '--consumer_name', consumer_name, '--provider_name', provider_name, '--test_type', test_type, '--test_name', test_name, '--network_name', network_name, '--alias_name', resource_name]
        else:
            consumer_run_cmd = ['docker', 'run', '-d', '--rm', '--name', consumer_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-h', resource_name, consumer_tag]
            consumer_exec_cmd = ['docker', 'exec', consumer_name,'python', 'setup_topo.py', '--database_type', database_type, '--is_consumer', '--consumer_name', consumer_name, '--provider_name', provider_name, '--network_name', network_name, '--alias_name', resource_name]
        
        print(consumer_exec_cmd)
        consumer_stop_cmd = ['docker', 'stop', consumer_name]
        consumer_str = 'consumer-' + str(i)
        docker_cmd = get_docker_cmd(consumer_str, test_type, consumer_exec_cmd, consumer_stop_cmd, consumer_name)
        docker_run_list.append(consumer_run_cmd)
        docker_cmds_list.append(docker_cmd)

    run_pool = Pool(processes=int(4))
    run_procs = [Popen(docker_cmd, stdout=PIPE, stderr=PIPE) for docker_cmd in docker_run_list]
    containers = [{'test_type': docker_cmd['test_type'], 'resource_type':docker_cmd['resource_type'], 'proc': run_pool.apply_async(run_command_in_container, (docker_cmd['exec_cmd'], docker_cmd['stop_cmd'], docker_cmd['container_name']))} for docker_cmd in docker_cmds_list]
    container_error_codes = [{'test_type': c['test_type'], 'resource_type': c['resource_type'],'error_code': c['proc'].get()} for c in containers]
    #print(container_error_codes)
    check_topo_state(machine_list, network_name, container_error_codes)

    #sys.exit(1)

def check_topo_state(machine_list, network_name, container_error_codes):
    failures = []
    for machine_name in machine_list:
        for ec in container_error_codes:
            if ec['error_code'] != 0 and ec['resource_type'] == 'provider' and ec['test_type'] == 'topology_icat':
                failures.append(ec['resource_type'])
    
    rm_network = Popen(['docker', 'network', 'rm', network_name], stdout=PIPE, stderr=PIPE)
    rm_network.wait()
    if len(failures) > 0:
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

