#!/usr/bin/python

from __future__ import print_function

import argparse
import os
import subprocess
from subprocess import Popen, PIPE

def build_externals( output_directory):
    build_hook = 'irods_consortium_continuous_integration_build_hook.py'
    if os.path.exists('/irods_externals/irods_consortium_continuous_integration_build_hook.py'):
        build_cmd = ['cd irods_externals; python {0} --output_root_directory {1}'.format(build_hook, output_directory)]
        build_p = subprocess.check_call(build_cmd, shell=True)
    

def main():
    parser = argparse.ArgumentParser(description='build plugins in os-containers')
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    build_externals(args.output_directory)

if __name__ == '__main__':
    main()
