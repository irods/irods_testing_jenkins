#!/usr/bin/python

from __future__ import print_function

import configuration
import argparse
import subprocess

def build_irods_in_containers(base_os, build_id, irods_repo, irods_commitish, icommands_repo, icommands_commitish, output_directory):
    build_tag = base_os +'-irods-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + build_id 
    docker_cmd = ['docker build -t {0} --build-arg base_image={1} --build-arg arg_irods_repo={2} --build-arg arg_irods_commitish={3} --build-arg arg_icommands_repo={4} --build-arg arg_icommands_commitish={5} -f Dockerfile.build_irods .'.format(build_tag, base_image, irods_repo, irods_commitish, icommands_repo, icommands_commitish)] 
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    save_irods_build(build_tag, output_directory)

def save_irods_build(image_name, output_directory):
    save_cmd = ['docker run --rm -v {0}:/jenkins_output {1}'.format(output_directory, image_name)] 
    save_build = subprocess.check_call(save_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--icommands_repo', type = str, required=True)
    parser.add_argument('--icommands_commitish', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    print(args.irods_repo)
    print(args.irods_commitish)
    print(args.icommands_repo)
    print(args.icommands_commitish)
    build_irods_in_containers(args.platform_target, args.build_id, args.irods_repo, args.irods_commitish, args.icommands_repo, args.icommands_commitish, args.output_directory)
   
if __name__ == '__main__':
    main()

