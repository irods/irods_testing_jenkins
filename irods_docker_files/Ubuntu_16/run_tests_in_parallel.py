#!/usr/bin/python
from __future__ import print_function

from subprocess import Popen, PIPE
import sys
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--image_name', default='ubuntu_16:latest', help='base image name', required=True)
    parser.add_argument('-j', '--jenkins_output', default='/jenkins_output', help='jenkins output directory on the host machine', required=True)
    parser.add_argument('-t', '--test_name_prefix', help='test name prefix')
    parser.add_argument('-b', '--build_dir', default='Ubuntu_16', help='irods build directory', required=True)
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    args = parser.parse_args()


    image_name = args.image_name
    jenkins_output = args.jenkins_output
    prefix = args.test_name_prefix
    build_dir = args.build_dir
    database_type = args.database_type

    test_list = ['test_ssl', 'test_iadmin', 'test_resource_types', 'test_catalog',
                 'test_rulebase', 'test_symlink_operations', 'test_resource_tree', 'test_load_balanced_suite',
                 'test_icommands_file_operations', 'test_imeta_set', 'test_all_rules', 'test_iscan', 'test_ipasswd',
                 'test_ichmod', 'test_iput_options', 'test_ireg', 'test_irsync', 'test_iticket', 'test_irodsctl',
                 'test_resource_configuration', 'test_control_plane', 'test_native_rule_engine_plugin', 'test_quotas',
                 'test_ils', 'test_irmdir', 'test_ichksum', 'test_iquest', 'test_imeta_help', 'test_irepl', 'test_itrim','test_irm']

    #test_list = ['test_iadmin', 'test_all_rules']
    
    docker_run_list = []
    for test in test_list:
        test_name = prefix+'_'+test
        volume_mount = jenkins_output + ':/irods_build'

        cmd = ['docker', 'run', '--name', test_name, '-v', volume_mount, image_name, build_dir, database_type, test]
        docker_run_list.append(cmd)
    
    #print(docker_run_list)  
    
    procs_list = [Popen(docker_cmd, stdout=PIPE, stderr=PIPE) for docker_cmd in docker_run_list]
    exit_codes = [proc.wait() for proc in procs_list]

    tests_failed = []
    for test in test_list:
        test_name = prefix+'_'+test
        cmd = ['docker', 'inspect', test_name, "--format='{{.State.ExitCode}}'"]
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        output, err = proc.communicate()
        if output == "'0'\n":
            p = Popen(['docker', 'rm', test_name], stdout=PIPE, stderr=PIPE)
        else:
            test_failed = test + " : Failed"
            tests_failed.append(test_failed)

    if len(tests_failed) > 0:
        print(tests_failed)
        sys.exit(1)
 
if __name__ == '__main__':
    main()
