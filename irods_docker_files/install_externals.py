#!/usr/bin/python
from __future__ import print_function

import argparse
import os
import glob
import irods_python_ci_utilities

def install_externals(externals_dir, externals_to_install):
    package_suffix = irods_python_ci_utilities.get_package_suffix()
    os_specific_directory = irods_python_ci_utilities.append_os_specific_directory(externals_dir)
    externals = []
    externals_list = externals_to_install.split(',')
    for irods_externals in externals_list:
        externals.append(glob.glob(os.path.join(os_specific_directory, irods_externals + '.{0}'.format(package_suffix)))[0])

    irods_python_ci_utilities.install_os_packages_from_files(externals)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--externals_root_directory', default=None, help='externals directory')
    parser.add_argument('--externals_to_install', type=str, default=None, help='list of externals to be installed')
    args = parser.parse_args()
    install_externals(args.externals_root_directory, args.externals_to_install)

if __name__ == '__main__':
    main()
