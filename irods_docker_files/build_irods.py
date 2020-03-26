#!/usr/bin/python

from __future__ import print_function

import argparse
import os
import subprocess
from subprocess import Popen, PIPE

def build_irods(output_directory, icommands_git_repo, icommands_sha, externals_build_dir):
    build_hook = '/irods_git_repo/irods_consortium_continuous_integration_build_hook.py'
    if os.path.exists(build_hook):
        build_cmd = ['python2 {build_hook} --icommands_git_repository {icommands_git_repo} --icommands_git_commitish {icommands_sha} --externals_packages_directory {externals_build_dir} --output_root_directory {output_directory}'.format(**locals())]
        print('build_cmd ---> ', build_cmd)
        build_p = subprocess.check_call(build_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='build plugins in os-containers')
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    parser.add_argument('--icommands_git_commitish', type=str, required=True)
    parser.add_argument('--icommands_git_repository', type=str, required=True)
    parser.add_argument('-e', '--externals_packages_directory', type=str, default=None)
    args = parser.parse_args()
    build_irods(args.output_directory, args.icommands_git_repository, args.icommands_git_commitish, args.externals_packages_directory)

if __name__ == '__main__':
    main()
