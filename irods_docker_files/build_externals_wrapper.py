#!/usr/bin/python

from __future__ import print_function

import configuration
import argparse
import subprocess

def build_externals_in_containers(base_os, build_id, externals_repo, externals_commitish, output_directory, machine_name):
    build_tag = base_os + '-externals-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + build_id 
    docker_cmd = ['docker build -t {0} --build-arg base_image={1} --build-arg arg_externals_repo={2} --build-arg arg_externals_commitish={3} -f Dockerfile.externals .'.format(build_tag, base_image, externals_repo, externals_commitish)] 
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    externals_build_dir = '/{0}/{1}'.format(output_directory, 'irods-externals')
    save_externals_build(build_tag, externals_build_dir, machine_name)

def save_externals_build(image_name, output_directory, machine_name):
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
    run_cmd = ['docker run --privileged -d --rm --name {0} -v {1}:/externals_build_output -v {2} -v /tmp/$(mktemp -d):/run {3}'.format(machine_name, output_directory, cgroup_mount, image_name)]

    exec_cmd = ['docker exec {0} python build_externals.py --output_directory /externals_build_output'.format(machine_name)]

    stop_cmd = ['docker stop {0}'.format(machine_name)]

    run_image = subprocess.check_call(run_cmd, shell=True)
    save_build = subprocess.check_call(exec_cmd, shell=True)
    stop = subprocess.check_call(stop_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--externals_repo', type=str, required=True)
    parser.add_argument('--externals_commitish', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    machine_name = args.platform_target + '-externals-' + args.build_id
    build_externals_in_containers(args.platform_target, args.build_id, args.externals_repo, args.externals_commitish, args.output_directory, machine_name)
   
if __name__ == '__main__':
    main()

