#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import json
import sys
import time
import ci_utilities
import docker_cmds_utilities

from subprocess import Popen, PIPE
from multiprocessing import Pool
from docker_cmd_builder import DockerCommandsBuilder

def get_build_tag(base_os, stage, build_id):
    build_tag = base_os + '-' + stage + ':' + build_id
    return build_tag

def get_base_image(base_os, image_tag):
    base_image = base_os + ':' + image_tag
    return base_image

def build_zones(cmd_line_args):
    base_image = get_base_image(cmd_line_args.platform_target, cmd_line_args.image_tag)
    federation_tag_list=[]
    for x in range(cmd_line_args.zones):
        zone_id = x + 1
        stage = 'federation_zone_' + str(zone_id)
        federation_tag = get_build_tag(cmd_line_args.platform_target, stage, cmd_line_args.build_id)
        docker_cmds_utilities.build_irods_zone(federation_tag, base_image, cmd_line_args.database_type, 'Dockerfile.fed')
        federation_tag_list.append(federation_tag)

    network_name = cmd_line_args.platform_target + '_' + cmd_line_args.test_type + '_' + cmd_line_args.database_type + '_' + cmd_line_args.build_id
    create_federation(federation_tag_list, network_name, cmd_line_args)

def create_federation(federation_tag_list, network_name, cmd_line_args):
    docker_cmds_list = []
    machine_list = []
    build_mount = cmd_line_args.irods_build_dir + ':/irods_build'
    results_mount = cmd_line_args.output_directory + ':/irods_test_env' 
    upgrade_mount = None
    run_mount = None
    externals_mount = None
    mysql_mount = '/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz:/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz'

    zone1 = 'tempZone'
    zone2 = 'otherZone'
    platform_target = cmd_line_args.platform_target
    test_name_prefix = cmd_line_args.test_name_prefix

    docker_cmds_utilities.create_network(network_name)

    for i, federation_tag in enumerate(federation_tag_list, start=1):
        zone_name = zone2
        federated_zone_name = 'icat.otherZone.example.org'
        remote_federated_zone = platform_target + '-' + test_name_prefix + '-' + zone1
        database_container = platform_target + '_' + cmd_line_args.test_name_prefix + '_otherZone_' + cmd_line_args.database_type + '-database'
        if i == 1:
            zone_name = zone1
            federated_zone_name = 'icat.tempZone.example.org'
            remote_federated_zone = platform_target + '-' + test_name_prefix + '-' + zone2
            database_container = platform_target + '_' + cmd_line_args.test_name_prefix + '_tempZone_' + cmd_line_args.database_type + '-database'

        docker_cmds_utilities.run_database(cmd_line_args.database_type, database_container, federated_zone_name, network_name)

        federation_name = platform_target + '-' + test_name_prefix + '-' + zone_name
        machine_list.append(federation_name)

        cmdsBuilder = DockerCommandsBuilder()
        cmdsBuilder.core_constructor(federation_name, build_mount, upgrade_mount, results_mount, run_mount, externals_mount, mysql_mount, federation_tag, 'setup_fed_and_test.py', cmd_line_args.database_type, cmd_line_args.specific_test, cmd_line_args.test_type, False, True, database_container)
        cmdsBuilder.set_hostname(federated_zone_name)
        cmdsBuilder.set_zone_name(zone_name)
        cmdsBuilder.set_remote_zone(remote_federated_zone)

        federation_run_cmd = cmdsBuilder.build_run_cmd()
        federation_exec_cmd = cmdsBuilder.build_exec_cmd()
        federation_stop_cmd = cmdsBuilder.build_stop_cmd()

        print(federation_run_cmd)
        print(federation_exec_cmd)
        print(federation_stop_cmd)

        extra_args = {'remote_zone': remote_federated_zone, 'test_type': cmd_line_args.test_type, 'test_name': cmd_line_args.specific_test}
        docker_cmd = docker_cmds_utilities.get_docker_cmd(federation_run_cmd, federation_exec_cmd, federation_stop_cmd, federation_name, federated_zone_name, database_container, cmd_line_args.database_type, network_name, extra_args)
        docker_cmds_list.append(docker_cmd)

    run_pool = Pool(processes=int(2))
    

    containers = [{'alias_name': docker_cmd['alias_name'], 'proc': run_pool.apply_async(docker_cmds_utilities.run_command_in_container, (docker_cmd['run_cmd'], docker_cmd['exec_cmd'], docker_cmd['stop_cmd'], docker_cmd['container_name'], docker_cmd['alias_name'], docker_cmd['database_container'], docker_cmd['database_type'], docker_cmd['network_name'],), {'remote_zone': docker_cmd['remote_zone'], 'test_type': docker_cmd['test_type'], 'test_name': docker_cmd['test_name']})} for docker_cmd in docker_cmds_list]


    container_error_codes = [{'alias_name': c['alias_name'], 'error_code': c['proc'].get()} for c in containers]
    check_fed_state(machine_list, network_name, container_error_codes)

def check_fed_state(machine_list, network_name, container_error_codes):
    failures = []
    for machine_name in machine_list:
        for ec in container_error_codes:
            if ec['error_code'] != 0 and 'otherZone' in ec['alias_name']:
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
    parser.add_argument('--test_name_prefix', type=str)
    parser.add_argument('--test_type', type=str, required=False, choices=['standalone_icat', 'topology_icat', 'topology_resource', 'federation'])
    parser.add_argument('--specific_test', type=str)
    parser.add_argument('--zones', type=int, default=2, help='number of zones in the federation')
    parser.add_argument('--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=False)
    
    args = parser.parse_args()

    print('specific_test ', args.specific_test)
    print('test_type ' , args.test_type)

    build_zones(args)

        
if __name__ == '__main__':
    main()

