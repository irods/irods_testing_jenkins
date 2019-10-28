#!/usr/bin/python
from __future__ import print_function

import argparse
import subprocess
import socket
import shutil
import sys
import os
import time
import irods_python_ci_utilities
from subprocess import Popen, PIPE

def run_tests(test_type, specific_test, federation_args):
    test_type_dict = {
        'topology_icat': '--run_python_suite --include_auth_tests --topology_test=icat',
        'topology_resource': '--run_python_suite --include_auth_tests --topology_test=resource',
        'federation': '--run_specific_test test_federation --federation {0}'.format(' '.join(federation_args))
    }

    if specific_test is None or specific_test == 'None':
        test_type_argument = test_type_dict[test_type]
    else:
        if test_type == 'topology_icat': 
            test_type_argument = '--run_specific_test=' + specific_test + ' --topology_test=icat'
        elif test_type == 'topology_resource':
            test_type_argument = '--run_specific_test=' + specific_test + ' --topology_test=resource'
        else:
            test_type_argument = '--run_specific_test=' + specific_test + ' --federation {0}'.format(' '.join(federation_args))

    if test_type == 'federation':
        irods_version = irods_python_ci_utilities.get_irods_version()
        if irods_version < (4, 0): # we are running copied code on an old zone
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'mkdir -p /var/lib/irods/tests'], check_rc=True)
        if irods_version < (4, 2):
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'mkdir /var/lib/irods/log'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'echo "" > /var/lib/irods/scripts/irods/database_connect.py'], check_rc=True)
    
    try:
        test_output_file = '/var/lib/irods/log/test_output.log'
        run_test_cmd = ['su', '-', 'irods', '-c', 'cd scripts; python2 run_tests.py --xml_output {0} 2>&1 | tee {1}; exit $PIPESTATUS'.format(test_type_argument, test_output_file)]
        print(run_test_cmd)
        rc, stdout, stderr = irods_python_ci_utilities.subprocess_get_output(run_test_cmd)
        return rc
    finally:
        output_directory = '/irods_test_env/{0}/{1}'.format(irods_python_ci_utilities.get_irods_platform_string(), socket.gethostname())
        irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_directory, lambda x: True)
        shutil.copy('/var/lib/irods/log/test_output.log', output_directory)

def main():
    parser = argparse.ArgumentParser(description='Run topology/federation tests from Jenkins')
    parser.add_argument('--test_type', type=str, required=True, choices=['topology_icat', 'topology_resource', 'federation'])
    parser.add_argument('--specific_test', type=str, default=None)
    parser.add_argument('--federation_args', type=str, nargs=3, default='None')

    args = parser.parse_args()

    if not args.test_type == 'federation':
        if args.test_type == 'topology_icat':
            listen_cmd = ['nc', '-vz', 'resource1.example.org', '1247']
        else:
            listen_cmd = ['nc', '-vz', 'icat.example.org', '1247']

        status = 'refused'
        while status == 'refused':
            proc = subprocess.Popen(listen_cmd, stdout = PIPE, stderr = PIPE)
            _out, _err = proc.communicate()

            if 'open' in (_err):
                status = 'open'
            if not 'Connection refused' in (_err):
                status = 'open'
            time.sleep(1)
        
    rc = run_tests(args.test_type, args.specific_test, args.federation_args)
    sys.exit(rc)

if __name__ == '__main__':
    main()
