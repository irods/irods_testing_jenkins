os_identifier_dict = {
    'centos_7': 'centos:7',
    'ubuntu_14': 'ubuntu:14.04',
    'ubuntu_16': 'ubuntu:16.04',
    'ubuntu_18': 'ubuntu:18.04'
}

database_dict = {
    'mariadb': 'mariadb:10.1',
    'mysql': 'mysql:5.7',
    'postgres': 'postgres:10.12',
    'oracle': 'oracle/database:11.2.0.2-xe'
}

# change this to the dirname of the mysql odbc connector archive file
mysql_odbc_connectors = {
    'ubuntu_16': 'mysql-connector-odbc-5.3.13-linux-ubuntu16.04-x86-64bit',
    'ubuntu_18': 'mysql-connector-odbc-5.3.13-linux-ubuntu18.04-x86-64bit'
}
