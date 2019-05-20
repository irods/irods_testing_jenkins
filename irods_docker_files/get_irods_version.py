#!/usr/bin/python

import irods_python_ci_utilities

def get_irods_version():
    irods_version = irods_python_ci_utilities.get_irods_version()
    return irods_version

if __name__ == '__main__':
    irods_version = get_irods_version()
    print irods_version
