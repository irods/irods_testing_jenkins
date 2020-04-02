#!/usr/bin/python

# real modules
from __future__ import print_function
import argparse
import subprocess
import json
import sys
import time
from subprocess import Popen, PIPE
from multiprocessing import Pool

# local
import ci_utilities
import docker_cmds_utilities
from docker_cmd_builder import DockerCommandsBuilder

def build_topo_containers(cmd_line_args):
    base_image = ci_utilities.get_base_image(cmd_line_args.platform_target, cmd_line_args.image_tag)
    provider_tag = ci_utilities.get_build_tag(cmd_line_args.platform_target, 'topo_provider', cmd_line_args.database_type, cmd_line_args.build_id)
    docker_cmds_utilities.build_irods_zone(provider_tag, base_image, cmd_line_args.database_type, 'Dockerfile.topo', 'True')
    consumer_tag_list = []
    machine_list = []
    for x in range(cmd_line_args.consumers):
        consumer_id = x + 1
        stage = 'topo_consumer_' + str(consumer_id)
        consumer_tag = ci_utilities.get_build_tag(cmd_line_args.platform_target, stage, cmd_line_args.database_type, cmd_line_args.build_id)
        docker_cmds_utilities.build_irods_zone(consumer_tag, base_image, cmd_line_args.database_type, 'Dockerfile.topo', 'False')
        consumer_tag_list.append(consumer_tag)
        consumer_name = cmd_line_args.platform_target + '-' + cmd_line_args.test_name_prefix + '-consumer-' + str(consumer_id)
        machine_list.append(consumer_name)

    network_name = cmd_line_args.platform_target + '_' + cmd_line_args.test_type + '_' + cmd_line_args.database_type + '_' + cmd_line_args.build_id
    create_topology(cmd_line_args, provider_tag, consumer_tag_list, machine_list, network_name)

def create_topology(cmd_line_args, provider_tag, consumer_tag_list, machine_list, network_name):
    docker_run_list = []
    docker_cmds_list = []
    build_mount = cmd_line_args.irods_build_dir + ':/irods_build'
    results_mount = cmd_line_args.output_directory + ':/irods_test_env'

    if cmd_line_args.upgrade_packages_dir == None:
        upgrade_mount = None
    else:
        upgrade_packages_dir = cmd_line_args.upgrade_packages_dir
        upgrade_mount = upgrade_packages_dir + ':/upgrade_dir'

    run_mount = None
    externals_mount = None
    mysql_mount = '/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz:/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz'

    provider_name = cmd_line_args.platform_target + '-' + cmd_line_args.test_name_prefix + '-provider'
    machine_list.append(provider_name)

    database_container = cmd_line_args.platform_target + '_' + cmd_line_args.test_name_prefix + '_' + cmd_line_args.test_type + '_' + cmd_line_args.database_type + '-database'
    cmdsBuilder = DockerCommandsBuilder()
    cmdsBuilder.core_constructor(provider_name, build_mount, upgrade_mount, results_mount, run_mount, externals_mount, mysql_mount, provider_tag, 'setup_topo.py', cmd_line_args.database_type, cmd_line_args.specific_test, cmd_line_args.test_type, False, True, database_container)
    cmdsBuilder.set_machine_list(machine_list)
    cmdsBuilder.set_use_ssl(cmd_line_args.use_ssl)

    provider_run_cmd = cmdsBuilder.build_run_cmd()
    provider_exec_cmd = cmdsBuilder.build_exec_cmd()
    provider_stop_cmd = cmdsBuilder.build_stop_cmd()

    print('provider_run_cmd:    ' + str(provider_run_cmd))
    print('provider_exec_cmd:    ' + str(provider_exec_cmd))

    provider_alias = 'icat.example.org'

    extra_args = {
        'test_type': cmd_line_args.test_type,
        'machine_list': ' '.join(machine_list),
        'use_ssl': cmd_line_args.use_ssl
    }
    docker_cmd = docker_cmds_utilities.get_docker_cmd(provider_run_cmd, provider_exec_cmd, provider_stop_cmd, provider_name, provider_alias, database_container, cmd_line_args.database_type, network_name, extra_args)
    docker_cmds_list.append(docker_cmd)
    
    for i, consumer_tag in enumerate(consumer_tag_list):
        consumer_name = machine_list[i]
        resource_name = 'resource' + str(i+1) + '.example.org'
        cmdsBuilder.set_machine_name(consumer_name)
        cmdsBuilder.set_is_provider(False)
        cmdsBuilder.set_hostname(resource_name)
        cmdsBuilder.set_image_name(consumer_tag)
        consumer_run_cmd = cmdsBuilder.build_run_cmd()
        docker_run_list.append(consumer_run_cmd)
        consumer_exec_cmd = cmdsBuilder.build_exec_cmd()
        
        print('consumer_run_cmd:    ' + str(consumer_run_cmd))
        print('consumer_exec_cmd:    ' + str(consumer_exec_cmd))
        consumer_stop_cmd = cmdsBuilder.build_stop_cmd()
    
        docker_cmd = docker_cmds_utilities.get_docker_cmd(consumer_run_cmd, consumer_exec_cmd, consumer_stop_cmd, consumer_name, resource_name, database_container, cmd_line_args.database_type, network_name, extra_args)
        docker_cmds_list.append(docker_cmd)

    docker_cmds_utilities.create_network(network_name)
    docker_cmds_utilities.run_database(cmd_line_args.database_type, database_container, provider_alias, network_name)

    run_pool = Pool(processes=int(4))
    containers =  [
        {
            'test_type': docker_cmd['test_type'],
            'alias_name':docker_cmd['alias_name'],
            'proc': run_pool.apply_async(
                docker_cmds_utilities.run_command_in_container,
                (
                    docker_cmd['run_cmd'],
                    docker_cmd['exec_cmd'],
                    docker_cmd['stop_cmd'],
                    docker_cmd['container_name'],
                    docker_cmd['alias_name'],
                    docker_cmd['database_container'],
                    docker_cmd['database_type'],
                    docker_cmd['network_name'],
                ),
                {
                    'test_type': docker_cmd['test_type'],
                    'machine_list': docker_cmd['machine_list'],
                    'use_ssl': docker_cmd['use_ssl']
                }
            )
        } for docker_cmd in docker_cmds_list
    ]

    container_error_codes = [
        {
            'test_type': c['test_type'],
            'alias_name': c['alias_name'],
            'error_code': c['proc'].get()
        } for c in containers
    ]
    print(container_error_codes)

    check_topo_state(machine_list, network_name, container_error_codes)

def check_topo_state(machine_list, network_name, container_error_codes):
    print("check_topo_state")

    failures = []
    for machine_name in machine_list:
        for ec in container_error_codes:
            if ec['error_code'] != 0 and ec['alias_name'] == 'icat.example.org' and ec['test_type'] == 'topology_icat':
                failures.append(ec['alias_name'])
            if ec['error_code'] != 0 and ec['alias_name'] == 'resource1.example.org' and ec['test_type'] == 'topology_resource':
                failures.append(ec['alias_name'])
    
    if len(failures) > 0:
        sys.exit(1)

    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='Run tests in os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('--image_tag', type=str, required=True, help='Tag id or name for the base image')
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_build_dir', type=str, required=True)
    parser.add_argument('--upgrade_packages_dir', required=False, default=None)
    parser.add_argument('--test_name_prefix', type=str)
    parser.add_argument('--test_type', type=str, required=False, choices=['standalone_icat', 'topology_icat', 'topology_resource', 'federation'])
    parser.add_argument('--specific_test', type=str)
    parser.add_argument('--consumers', type=int, default=3, help='number of consumers')
    parser.add_argument('--providers', type=int, default=1, help='number of providers')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=False)
    parser.add_argument('--use_ssl', action='store_true', default=False)
    
    args = parser.parse_args()

    print('specific_test ', args.specific_test)
    print('test_type ' , args.test_type)
    print('use_ssl ', args.use_ssl)

    build_topo_containers(args)

if __name__ == '__main__':
    main()

