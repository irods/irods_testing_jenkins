#!/usr/bin/python
from __future__ import print_function

import argparse
import irods_python_ci_utilities
import subprocess
import time

from subprocess import Popen, PIPE

def install_database(database):
    distribution = irods_python_ci_utilities.get_distribution()
    if database == 'postgres':
        if distribution == 'Ubuntu':
            irods_python_ci_utilities.install_os_packages(['postgresql', 'postgresql-contrib', 'odbc-postgresql', 'unixodbc', 'super'])
            start_db = subprocess.Popen(['service', 'postgresql', 'start'])
            start_db.wait()
            status = 'no response'
            while status == 'no response':
                status_db = subprocess.Popen(['pg_isready'], stdout=PIPE, stderr=PIPE)
                out, err = status_db.communicate()
                if 'accepting connections' in out:
                    status = out
         
        elif distribution == 'Centos' or distribution == 'Centos linux':
             irods_python_ci_utilities.install_os_packages(['postgresql-server', 'postgresql-contrib'])
             irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c' '"initdb"'], check_rc=True)
             irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "pg_ctl -D /var/lib/pgsql/data -l logfile start"], check_rc=True)
             time.sleep(5)


def configure_database(database):
    if database == 'postgres':
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "createuser -s irods"], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', '''psql -c "alter role irods with password 'testpassword'"'''], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "createdb 'ICAT'"], check_rc=True)
        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--install_database', default='True')
    args = parser.parse_args()

    database_type = args.database_type
    print('lets try installing a database ', args.install_database)    
    if args.install_database == 'True':
        install_database(database_type)
        configure_database(database_type)
    
if __name__ == '__main__':
    main()
