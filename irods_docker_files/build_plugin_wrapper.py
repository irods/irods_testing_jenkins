#!/usr/bin/python

from __future__ import print_function

import configuration
import argparse
import subprocess

def build_plugins_in_containers(base_os, build_id, plugin_repo, plugin_commitish, irods_packages_directory, output_directory):
    _git_repo = plugin_repo.split('/')
    plugin_name = _git_repo[len(_git_repo) - 1]

    build_tag = base_os + '-' + plugin_name +'-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + build_id 
    docker_cmd = ['docker build -t {0} --build-arg base_image={1} --build-arg arg_plugin_repo={2} --build-arg arg_plugin_commitish={3} -f Dockerfile.build_plugin .'.format(build_tag, base_image, plugin_repo, plugin_commitish)] 
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    _git_repo = plugin_repo.split('/')
    plugin_name = _git_repo[len(_git_repo) - 1]
    plugin_build_dir = '/{0}/{1}'.format(output_directory, plugin_name)
    save_plugin_build(build_tag, irods_packages_directory, plugin_build_dir)

def save_plugin_build(image_name, irods_packages_directory, output_directory):
    save_cmd = ['docker run --rm -v {0}:/irods_build -v {1}:/plugin_build_output {2} -o /plugin_build_output -b /irods_build'.format(irods_packages_directory, output_directory, image_name)] 
    save_build = subprocess.check_call(save_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--plugin_repo', type=str, required=True)
    parser.add_argument('--plugin_commitish', type=str, required=True)
    parser.add_argument('--irods_packages_build_directory', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    build_plugins_in_containers(args.platform_target, args.build_id, args.plugin_repo, args.plugin_commitish, args.irods_packages_build_directory, args.output_directory)
   
if __name__ == '__main__':
    main()

