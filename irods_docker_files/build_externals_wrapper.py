#!/usr/bin/python

from __future__ import print_function

import ci_utilities
import configuration
import argparse
import subprocess
import sys
from subprocess import Popen, PIPE

def build_externals_in_containers(base_os, build_id, externals_repo, externals_sha, output_directory, machine_name):
    build_tag = base_os + '-externals-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + build_id 
    docker_cmd = ['docker build -t {build_tag} --build-arg base_image={base_image} --build-arg arg_externals_repo={externals_repo} --build-arg arg_externals_commitish={externals_sha} -f Dockerfile.externals .'.format(**locals())] 
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    externals_build_dir = '/{0}/{1}'.format(output_directory, 'irods-externals')
    save_externals_build(build_tag, externals_build_dir, machine_name)

def save_externals_build(image_name, output_directory, machine_name):
    cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
    output_mount = '{0}:/externals_build_output'.format(output_directory)
    run_cmd = ['docker', 'run', '--privileged', '-d', '--rm', '--name',
               machine_name, '-v', output_mount, '-v', cgroup_mount, image_name]
    print(run_cmd)
    exec_cmd = ['docker', 'exec', machine_name, 'python', 'build_externals.py', '--output_directory', '/externals_build_output']
    print(exec_cmd)
    stop_cmd = ['docker', 'stop', machine_name]

    run_image = Popen(run_cmd, stdout=PIPE, stderr=PIPE).wait()
    save_build = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _sout, _serr = save_build.communicate()
    rc = save_build.returncode
    if rc != 0:
        print('output from save_build...')
        print('stdout:[' + str(_sout) + ']')
        print('stderr:[' + str(_serr) + ']')
        print('return code:[' + str(rc) + ']')
    stop = Popen(stop_cmd, stdout=PIPE, stderr=PIPE).wait()
    sys.exit(rc)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--externals_repo', type=str, required=True)
    parser.add_argument('--externals_commitish', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    machine_name = args.platform_target + '-externals-' + args.build_id
    externals_sha = ci_utilities.get_sha_from_commitish(args.externals_repo, args.externals_commitish)
    build_externals_in_containers(args.platform_target, args.build_id, args.externals_repo, externals_sha, args.output_directory, machine_name)
   
if __name__ == '__main__':
    main()

