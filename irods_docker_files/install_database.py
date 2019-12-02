#!/usr/bin/python
from __future__ import print_function

import argparse
import irods_python_ci_utilities
import subprocess
import os
import tempfile
import time

from subprocess import Popen, PIPE

def install_oracle_dependencies_yum():
    tar_file = os.path.expanduser('/oci.tar')
    irods_python_ci_utilities.subprocess_get_output(['wget', 'http://people.renci.org/~jasonc/irods/oci.tar', '-O', tar_file], check_rc=True)
    tar_dir = os.path.expanduser('/oci')
    os.mkdir(tar_dir)
    irods_python_ci_utilities.subprocess_get_output(['tar', '-xf', tar_file, '-C', tar_dir], check_rc=True)
    irods_python_ci_utilities.install_os_packages(['unixODBC'])
    irods_python_ci_utilities.subprocess_get_output('rpm -i --nodeps {0}/*'.format(tar_dir), shell=True, check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['ln', '-s', '/usr/lib64/libodbcinst.so.2', '/usr/lib64/libodbcinst.so.1'], check_rc=True)

def install_oracle_dependencies_apt():
    tar_file = os.path.expanduser('/oci.tar')
    irods_python_ci_utilities.subprocess_get_output(['wget', 'http://people.renci.org/~jasonc/irods/oci.tar', '-O', tar_file], check_rc=True)
    tar_dir = os.path.expanduser('/oci')
    os.mkdir(tar_dir)
    irods_python_ci_utilities.subprocess_get_output(['tar', '-xf', tar_file, '-C', tar_dir], check_rc=True)
    Popen(['apt-get', 'update']).wait()
    irods_python_ci_utilities.install_os_packages(['alien', 'libaio1'])
    irods_python_ci_utilities.subprocess_get_output('alien -i {0}/*'.format(tar_dir), shell=True, check_rc=True)

def install_oracle_client():
    with tempfile.NamedTemporaryFile() as f:
        f.write('''
export LD_LIBRARY_PATH=/usr/lib/oracle/11.2/client64/lib:$LD_LIBRARY_PATH
export ORACLE_HOME=/usr/lib/oracle/11.2/client64
export PATH=$ORACLE_HOME/bin:$PATH
''')
        f.flush()
        irods_python_ci_utilities.subprocess_get_output(['su', '-c', "cat '{0}' >> /etc/profile.d/oracle.sh".format(f.name)], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-c', "echo 'ORACLE_HOME=/usr/lib/oracle/11.2/client64' >> /etc/environment"], check_rc=True)
        subprocess.check_call('mkdir -p /usr/lib/oracle/11.2/client64/network/admin', shell=True)
        tns_contents = '''
XE =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = oracle.example.org)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = XE)
    )
  )
'''
        irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-c', "echo '{0}' > /usr/lib/oracle/11.2/client64/network/admin/tnsnames.ora".format(tns_contents)], check_rc=True)

def install_database_apt(database):
    if database == 'postgres':
        irods_python_ci_utilities.subprocess_get_output(['apt-get', 'update'], check_rc=True)
        irods_python_ci_utilities.install_os_packages(['postgresql', 'postgresql-contrib', 'odbc-postgresql', 'unixodbc', 'super'])
        start_db = subprocess.Popen(['service', 'postgresql', 'start'])
        start_db.wait()
        status = 'no response'
        while status == 'no response':
            status_db = subprocess.Popen(['pg_isready'], stdout=PIPE, stderr=PIPE)
            out, err = status_db.communicate()
            if 'accepting connections' in out:
                status = out
            time.sleep(1)
    elif database == 'mysql':
        Popen(['/etc/init.d/apparmor', 'stop']).wait()
        Popen(['/etc/init.d/apparmor', 'teardown']).wait()
        irods_python_ci_utilities.subprocess_get_output(['sudo', 'debconf-set-selections'], data='mysql-server mysql-server/root_password password password', check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['sudo', 'debconf-set-selections'], data='mysql-server mysql-server/root_password_again password password', check_rc=True)
        Popen(['apt-get', 'update']).wait()
        Popen(['apt-get', 'install', '-y', 'mysql-server']).wait()
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'root', '-c', "echo '[mysqld]' > /etc/mysql/conf.d/irods.cnf"], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'root', '-c', "echo 'log_bin_trust_function_creators=1' >> /etc/mysql/conf.d/irods.cnf"], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['systemctl', 'restart', 'mysql'], check_rc=True)
        install_mysql_pcre(['libpcre3-dev', 'libmysqlclient-dev', 'build-essential', 'libtool', 'autoconf', 'unixodbc'], 'mysql')
        if irods_python_ci_utilities.get_distribution_version_major() == '16':
            tar_output_dir = tempfile.mkdtemp(prefix='irods_mysql_connector_tar_extraction')
            irods_python_ci_utilities.subprocess_get_output(['tar', 'xf', '/projects/irods/vsphere-testing/externals/mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit.tar.gz', '--directory', tar_output_dir], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'cp', os.path.join(tar_output_dir, 'mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit', 'lib', 'libmyodbc5a.so'), '/usr/lib'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'cp', os.path.join(tar_output_dir, 'mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit', 'lib', 'libmyodbc5S.so'), '/usr/lib'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'cp', os.path.join(tar_output_dir, 'mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit', 'lib', 'libmyodbc5w.so'), '/usr/lib'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'ln', '-s', '/var/run/mysqld/mysqld.sock', '/tmp/mysql.sock'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', os.path.join(tar_output_dir, 'mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit', 'bin', 'myodbc-installer'), '-d', '-a', '-n', 'MySQL ODBC 5.3 Unicode Driver', '-t', 'DRIVER=/usr/lib/libmyodbc5w.so;SETUP=/usr/lib/myodbc5S.so'], check_rc=True)
            irods_python_ci_utilities.subprocess_get_output(['sudo', os.path.join(tar_output_dir, 'mysql-connector-odbc-5.3.7-linux-ubuntu16.04-x86-64bit', 'bin', 'myodbc-installer'), '-d', '-a', '-n', 'MySQL ODBC 5.3 ANSI Driver', '-t', 'DRIVER=/usr/lib/libmyodbc5a.so;SETUP=/usr/lib/myodbc5S.so'], check_rc=True)
    elif database == 'oracle':
        install_oracle_dependencies()
        install_oracle_client()

def install_database_yum(database):
    if database == 'postgres':
        irods_python_ci_utilities.install_os_packages(['postgresql-server', 'postgresql-contrib'])
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c' '"initdb"'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "pg_ctl -D /var/lib/pgsql/data -l logfile start"], check_rc=True)
        status = 'no server running'
        while status == 'no server running':
            db_status = subprocess.Popen(['su', '-', 'postgres', '-c', "pg_ctl -D /var/lib/pgsql/data -l logfile status"], stdout=PIPE, stderr=PIPE)
            _out, _err = db_status.communicate()
            if 'server is running' in _out and '/usr/bin/postgres "-D" "/var/lib/pgsql/data"' in _out:
                status = _out
            time.sleep(1)
    elif database == 'mysql':
        Popen(['yum', 'upgrade', '-y']).wait()
        Popen(['yum', 'install', '-y', 'mariadb-server', 'mariadb-client']).wait()
        Popen(['systemctl', 'enable', 'mariadb']).wait()
        irods_python_ci_utilities.subprocess_get_output(['systemctl', 'start', 'mariadb'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['mysqladmin', '-u', 'root', 'password', 'password'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['sed', '-i', r's/\[mysqld\]/\[mysqld\]\nlog_bin_trust_function_creators=1/', '/etc/my.cnf'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['systemctl', 'restart', 'mariadb'], check_rc=True)
        install_mysql_pcre(['pcre-devel', 'gcc', 'make', 'automake', 'mysql-devel', 'libtool', 'autoconf'], 'mariadb')
    elif database == 'oracle':
        install_oracle_dependencies()
        install_oracle_client()

def install_database_zypper(database):
    print("not yet implemented")

def install_database(database):
    dispatch_map = {
        'Ubuntu': install_database_apt,
        'Centos': install_database_yum,
        'Centos linux': install_database_yum,
        'Opensuse': install_database_zypper,
    }

    try:
        return dispatch_map[irods_python_ci_utilities.get_distribution()](database)
    except KeyError:
        irods_python_ci_utilities.raise_not_implemented_for_distribution()

def install_oracle_dependencies():
    dispatch_map = {
        'Ubuntu': install_oracle_dependencies_apt,
        'Centos': install_oracle_dependencies_yum,
        'Centos linux': install_oracle_dependencies_yum,
    }

    try:
        return dispatch_map[irods_python_ci_utilities.get_distribution()]()
    except KeyError:
        irods_python_ci_utilities.raise_not_implemented_for_distribution()

def install_mysql_pcre(dependencies, mysql_service):
        irods_python_ci_utilities.install_os_packages(dependencies)
        local_pcre_git_dir = os.path.expanduser('/lib_mysqludf_preg')
        irods_python_ci_utilities.subprocess_get_output(['git', 'clone', 'https://github.com/mysqludf/lib_mysqludf_preg.git', local_pcre_git_dir], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['git', 'checkout', 'lib_mysqludf_preg-1.1'], cwd=local_pcre_git_dir, check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['autoreconf', '--force', '--install'], cwd=local_pcre_git_dir, check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['./configure'], cwd=local_pcre_git_dir, check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['make', 'install'], cwd=local_pcre_git_dir, check_rc=True)
        irods_python_ci_utilities.subprocess_get_output('mysql --user=root --password="password" < installdb.sql', shell=True, cwd=local_pcre_git_dir, check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['systemctl', 'restart', mysql_service], check_rc=True)

def configure_database(database):
    if database == 'postgres':
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "createuser -s irods"], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', '''psql -c "alter role irods with password 'testpassword'"'''], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['su', '-', 'postgres', '-c', "createdb 'ICAT'"], check_rc=True)
    elif database == 'mysql':
        irods_python_ci_utilities.subprocess_get_output(['mysql', '--user=root', '--password=password', '-e', "grant all on ICAT.* to 'irods'@'localhost' identified by 'testpassword'"], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['mysql', '--user=root', '--password=password', '-e', 'flush privileges'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['mysql', '--user=root', '--password=password', '-e', 'drop database if exists ICAT;'], check_rc=True)
        irods_python_ci_utilities.subprocess_get_output(['mysql', '--user=root', '--password=password', '-e', 'create database ICAT character set latin1 collate latin1_general_cs;'], check_rc=True)
    else:
        print(database, ' not implemented')
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
