#!/usr/bin/python
from __future__ import print_function

import argparse
import subprocess
import os
import tempfile
import time

from subprocess import Popen, PIPE
def get_ipaddress(provider_machine, format_str):
    _out, _err = Popen(['docker', 'inspect', '--format', "'{0}'".format(format_str), provider_machine], stdout=PIPE, stderr=PIPE).communicate()
    return _out

def run_docker_command(docker_cmd):
    print(docker_cmd)
    exec_cmd = Popen(docker_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = exec_cmd.communicate()

    print('_out --> ', _out)
    print('_err --> ', _err)

def is_database_running(database_machine, cmd_str, output_str):
    status = 'no response'
    while status == 'no response':
        exec_cmd = ['docker', 'exec', database_machine]
        exec_cmd.extend(cmd_str)
        print(exec_cmd)
        status_db = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
        out, err = status_db.communicate()
        print('db status out --> ', out)
        print('db status err --> ', err)
        if output_str in out:
            status = out
        time.sleep(5)
    return True

def configure_database(database, database_machine, provider_machine, network_name):
    if database == 'postgres':
        is_database_running(database_machine, ['pg_isready'], 'accepting connections')

        run_docker_command(['docker', 'exec', database_machine, 'sh', '-c', '''su - postgres -c "createuser -s irods"'''])
        cmd =  '''docker exec -e PSQL="psql -c "''' + ''' -e ALTER_ROLE=\"alter role irods with password 'testpassword'\"''' + " {0} sh -c '".format(database_machine) + "su - postgres -c " + "\"$PSQL \\\"$ALTER_ROLE\\\"\"\'"
        print(cmd)
        subprocess.check_call(cmd, shell=True)

        run_docker_command(['docker', 'exec', database_machine, 'sh', '-c', '''su - postgres -c "createdb 'ICAT'"'''])
    elif database == 'mysql' or database == 'mariadb':
        cmd_str = ['mysqladmin', '--user=root', '--password=password', 'ping']

        is_database_running(database_machine, cmd_str, 'mysqld is alive')

        #run_docker_command(['docker', 'exec', database_machine, 'mysqladmin', '--user=root', '--password=password', 'ping'])
        format_str = '{{json .NetworkSettings.Networks.' + network_name + '.IPAddress}}'
        ip_address = get_ipaddress(provider_machine, format_str).strip()
        run_docker_command(['docker', 'exec', database_machine, 'mysql', '--user=root', '--password=password', '-e', 'drop database if exists ICAT;'])
        run_docker_command(['docker', 'exec', database_machine, 'mysql', '--user=root', '--password=password', '-e', 'create database ICAT character set latin1 collate latin1_general_cs;'])
        run_docker_command(['docker', 'exec', database_machine, 'mysql', '--user=root', '--password=password', '-e', "CREATE USER 'irods'@{0} IDENTIFIED BY 'testpassword';".format(ip_address)])
        run_docker_command(['docker', 'exec', database_machine, 'mysql', '--user=root', '--password=password', '-e', "GRANT ALL PRIVILEGES ON ICAT.* to 'irods'@{0};".format(ip_address)])
        run_docker_command(['docker', 'exec', database_machine, 'mysql', '--user=root', '--password=password', '-e', 'FLUSH PRIVILEGES;'])
    elif database == 'oracle':
        pass
    else:
        print(database, ' not implemented')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--database_type', default='postgres', help='database type', required=True)
    parser.add_argument('--database_machine', help='database container name', required=True)
    parser.add_argument('--provider_machine', help='provider container name', default=None)
    parser.add_argument('--network_name', help='network name', default=None)
    args = parser.parse_args()

    database_type = args.database_type
    configure_database(database_type, args.database_machine, args.provider_machine, args.network_name)
    
if __name__ == '__main__':
    main()
