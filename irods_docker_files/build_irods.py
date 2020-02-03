#!/usr/bin/python

from __future__ import print_function

import argparse
import ci_utilities
import configuration
import subprocess
import sys

def build_irods_in_containers(base_os, image_tag, build_id, irods_repo, irods_sha, icommands_repo, icommands_sha, output_directory):
    build_tag = base_os +'-irods-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + image_tag 

    docker_cmd = ['docker build -t {build_tag} --build-arg base_image={base_image} --build-arg arg_irods_repo={irods_repo} --build-arg arg_irods_commitish={irods_sha} --build-arg arg_icommands_repo={icommands_repo} --build-arg arg_icommands_commitish={icommands_sha} -f Dockerfile.build_irods .'.format(**locals())]
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    save_irods_build(build_tag, output_directory)

def save_irods_build(image_name, output_directory):
    save_cmd = ['docker run --rm -v {0}:/jenkins_output {1}'.format(output_directory, image_name)] 
    save_build = subprocess.check_call(save_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('--image_tag', type=str, required=True, help='Tag id or name for the base image')
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--icommands_repo', type = str, required=True)
    parser.add_argument('--icommands_commitish', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    print('irods_repo:'+args.irods_repo)
    print('irods_commitish:'+args.irods_commitish)
    print('icommands_repo:'+args.icommands_repo)
    print('icommands_commitish:'+args.icommands_commitish)

    irods_sha = ci_utilities.get_sha_from_commitish(args.irods_repo, args.irods_commitish)
    icommands_sha = ci_utilities.get_sha_from_commitish(args.icommands_repo, args.icommands_commitish)

    build_irods_in_containers(args.platform_target, args.image_tag, args.build_id, args.irods_repo, irods_sha, args.icommands_repo, icommands_sha, args.output_directory)
   
if __name__ == '__main__':
    main()

