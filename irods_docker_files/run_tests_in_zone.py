#!/usr/bin/python
from __future__ import print_function

import argparse
import subprocess
import socket
import shutil
import sys
import time
import irods_python_ci_utilities
from subprocess import Popen, PIPE

def run_tests(test_type, specific_test):
    test_type_dict = {
        'topology_icat': '--run_python_suite --include_auth_tests --topology_test=icat',
        'topology_resource': '--run_python_suite --include_auth_tests --topology_test=resource',
    }

    if specific_test is not None or specific_test != 'None':
        if test_type == 'topology_icat': 
            test_type_argument = '--run_specific_test=' + specific_test + ' --topology_test=icat'
        else:
            test_type_argument = '--run_specific_test=' + specific_test + ' --topology_test=resource'
    else:
        test_type_argument = test_type_dict[test_type]

    try:
        test_output_file = '/var/lib/irods/log/test_output.log'
        rc, stdout, stderr = irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'cd scripts; python2 run_tests.py --xml_output {0} 2>&1 | tee {1}; exit $PIPESTATUS'.format(test_type_argument, test_output_file)])
        return rc
    finally:
        output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(), socket.gethostname())
        irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_directory, lambda x: True)
        shutil.copy('/var/lib/irods/log/test_output.log', output_directory)

def main():
    parser = argparse.ArgumentParser(description='Run topology/federation tests from Jenkins')
    parser.add_argument('--test_type', type=str, required=True, choices=['topology_icat', 'topology_resource', 'federation'])
    parser.add_argument('--specific_test', type=str)

    args = parser.parse_args()

    if args.test_type == 'topology_icat':
        listen_cmd = ['nc', '-vz', 'resource1.example.org', '1247']
    else:
        listen_cmd = ['nc', '-vz', 'icat.example.org', '1247']

    status = 'refused'
    while status == 'refused':
        proc = subprocess.Popen(listen_cmd, stdout = PIPE, stderr = PIPE)
        _out, _err = proc.communicate()
        print('_out ', _out)
        print('_err ', _err)

        if 'open' in (_err):
            status = 'open'
        if not 'Connection refused' in (_err):
            status = 'open'
        time.sleep(1)

    rc = run_tests(args.test_type, args.specific_test)
    sys.exit(rc)


if __name__ == '__main__':
    main()
