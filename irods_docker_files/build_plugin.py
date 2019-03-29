#!/usr/bin/python

from __future__ import print_function

import argparse
import os
import subprocess
from subprocess import Popen, PIPE

def build_plugin(irods_build_directory, output_directory):
    build_hook = '/irods_plugin/irods_consortium_continuous_integration_build_hook.py'
    if os.path.exists(build_hook):
        build_cmd = ['python {0} --irods_packages_root_directory {1} --output_root_directory {2}'.format(build_hook, irods_build_directory, output_directory)]
        build_p = subprocess.check_call(build_cmd, shell=True)
    

def main():
    parser = argparse.ArgumentParser(description='build plugins in os-containers')
    parser.add_argument('-o', '--output_directory', type=str, required=True)
    parser.add_argument('-b', '--irods_build_directory', type=str, required=True)

    args = parser.parse_args()
    build_plugin(args.irods_build_directory, args.output_directory)

if __name__ == '__main__':
    main()
