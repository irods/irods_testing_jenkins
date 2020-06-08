#!/usr/bin/python

from __future__ import print_function

import configuration
import argparse
import subprocess

def build_os_containers(platform_target, build_id):
    base_os = configuration.os_identifier_dict[platform_target]
    dockerfile = 'Dockerfile.ubuntu'
    if 'centos' in platform_target:
        dockerfile = 'Dockerfile.centos'
    if 'opensuse' in platform_target:
        dockerfile = 'Dockerfile.suse'

    build_tag = platform_target+':'+build_id
    docker_cmd = ['docker build -t {0} --build-arg base_image={1} -f {2} .'.format(build_tag, base_os, dockerfile)] 
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build base os-containers')
    parser.add_argument('-p','--platform_target', type=str, required=True)
    parser.add_argument('-b','--build_id', type=str, required=True)

    args = parser.parse_args()
    build_os_containers(args.platform_target, args.build_id)
   
if __name__ == '__main__':
    main()
