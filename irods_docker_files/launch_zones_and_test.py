#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import json
import sys
import time

from subprocess import Popen, PIPE
from multiprocessing import Pool

def get_build_tag(base_os, stage, build_id):
    build_tag = base_os + '-' + stage + ':' + build_id
    return build_tag

def get_network_name(base_os, build_id):
    network_name = base_os + '_federation_net_' + build_id
    return network_name

def get_base_image(base_os, build_id):
    base_image = base_os + ':' + build_id
    return base_image

def get_test_name_prefix(base_os, prefix):
    test_name_prefix = base_os + '-' + prefix

def get_docker_cmd(zone, run_cmd, exec_cmd, stop_cmd, container_name):
    docker_cmd = {'zone_name': zone,
                  'run_cmd': run_cmd,
                  'exec_cmd': exec_cmd,
                  'stop_cmd': stop_cmd,
                  'container_name': container_name
                 }
    return docker_cmd

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

    # execute a command in the running container
    exec_proc = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _eout, _eerr = exec_proc.communicate()
    _rc = exec_proc.returncode
    # stop the container
    stop_proc = Popen(stop_cmd, stdout=PIPE, stderr=PIPE)
    return _rc

def build_federation(build_tag, base_image, database_type):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} --build-arg arg_database_type={2} -f Dockerfile.fed .'.format(build_tag, base_image, database_type)]
    run_build = subprocess.check_call(docker_cmd, shell = True)

def build_zones(platform_target, build_id, irods_build_dir, test_name_prefix, output_directory, database_type, zones, test_type, test_name):
    base_image = get_base_image(platform_target, build_id)
    federation_tag_list=[]
    for x in range(zones):
        zone_id = x + 1    
        stage = 'federation_zone_' + str(zone_id)
        federation_tag = get_build_tag(platform_target, stage, build_id)
        build_federation(federation_tag, base_image, database_type)
        federation_tag_list.append(federation_tag)

    network_name = get_network_name(platform_target, build_id)

    create_network(network_name)
    create_federation(federation_tag_list, network_name, test_name_prefix, output_directory, database_type, irods_build_dir, platform_target, test_type, test_name)

def create_network(network_name):
    docker_cmd = ['docker', 'network', 'create', '--attachable', network_name]
    network = subprocess.check_call(docker_cmd)

def create_federation(federation_tag_list, network_name, test_name_prefix, output_directory, database_type, irods_build_dir, platform_target, test_type, test_name):
    docker_cmds_list = []
    machine_list = []
    docker_socket = '/var/run/docker.sock:/var/run/docker.sock'
    build_mount = irods_build_dir + ':/irods_build'
    results_mount = output_directory + ':/irods_test_env' 
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'

    zone1 = 'tempZone'
    zone2 = 'otherZone'
    for i, federation_tag in enumerate(federation_tag_list, start=1):
        zone_name = zone2
        federated_zone_name = 'icat.otherZone.example.org'
        remote_federated_zone = platform_target + '-' + test_name_prefix + '-' + zone1
        if i == 1:
            zone_name = zone1
            federated_zone_name = 'icat.tempZone.example.org'
            remote_federated_zone = platform_target + '-' + test_name_prefix + '-' + zone2

        federation_name = platform_target + '-' + test_name_prefix + '-' + zone_name
        machine_list.append(federation_name)
    
        federation_run_cmd = ['docker', 'run', '--rm', '-d', '--name', federation_name, '-v', build_mount, '-v', docker_socket, '-v', results_mount, '-v', cgroup_mount, '-h', federated_zone_name, federation_tag]
        federation_exec_cmd = ['docker', 'exec', federation_name, 'python', 'setup_fed_and_test.py', '--database_type', database_type, '--test_type', test_type, '--test_name', test_name, '--federation_name', federation_name,'--network_name', network_name, '--zone_name', zone_name, '--alias_name', federated_zone_name, '--remote_zone', remote_federated_zone]
        federation_stop_cmd = ['docker', 'stop', federation_name]
        print(federation_exec_cmd)
        docker_cmd = get_docker_cmd(zone_name, federation_run_cmd, federation_exec_cmd, federation_stop_cmd, federation_name)
        docker_cmds_list.append(docker_cmd)

    run_pool = Pool(processes=int(2))

    containers = [{'zone_name': docker_cmd['zone_name'], 'proc': run_pool.apply_async(run_command_in_container, (docker_cmd['run_cmd'], docker_cmd['exec_cmd'], docker_cmd['stop_cmd'], docker_cmd['container_name']))} for docker_cmd in docker_cmds_list]
    container_error_codes = [{'zone_name': c['zone_name'], 'error_code': c['proc'].get()} for c in containers]
    check_fed_state(machine_list, network_name, container_error_codes)

def check_fed_state(machine_list, network_name, container_error_codes):
    failures = []
    for machine_name in machine_list:
        for ec in container_error_codes:
            if ec['error_code'] != 0 and ec['zone_name'] == 'otherZone':
                failures.append(ec['zone_name'])

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
    parser.add_argument('--zones', type=int, default=2, help='number of zones in the federation')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=False)
    
    args = parser.parse_args()

    print('specific_test ', args.specific_test)
    print('test_type ' , args.test_type)

    build_zones(args.platform_target, args.build_id, args.irods_build_dir, args.test_name_prefix, args.output_directory, args.database_type, args.zones, args.test_type, args.specific_test)

        
if __name__ == '__main__':
    main()

