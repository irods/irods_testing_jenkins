#!/usr/bin/python
from __future__ import print_function

import os
import subprocess
import platform
import sys
import json
import time

if sys.version_info < (3, 0):
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

from github import Github
from subprocess import Popen, PIPE

# Dereference commitish (branch name, SHA, partial SHA, etc.) to a full SHA
def get_sha_from_commitish(_repo, _commitish):
    try:
        repo = urlparse(_repo).path.strip('/')
        sha = Github().get_repo(repo).get_commit(_commitish).sha
        print('found [{_repo}@{_commitish}] as sha:{sha}'.format(**locals()))
        return sha
    except:
        print("Error getting SHA from repo [{0}] for commitish [{1}]. Please make sure URL and commitish are correct.".format(_repo, _commitish))
        print(sys.exc_info()[0], ': ', sys.exc_info()[1])
        return _commitish

def get_build_tag(base_os, stage, database_type, build_id):
    build_tag = base_os + '-' + stage + '-' + database_type + ':' + build_id
    return build_tag

def get_base_image(base_os, build_id):
    base_image = base_os + ':' + build_id
    return base_image

def get_irods_version():
    version = get_irods_version_from_json()
    if version:
        return version
    version = get_irods_version_from_bash()
    if version:
        return version
    raise RuntimeError('Unable to determine iRODS version')

def get_irods_version_from_json():
    try:
        with open('/var/lib/irods/VERSION.json.dist') as f:
            version_string = json.load(f)['irods_version']
    except IOError as e1:
        if e1.errno != 2:
            raise
        try:
            with open('/var/lib/irods/VERSION.json') as f:
                version_string = json.load(f)['irods_version']
        except IOError as e2:
            if e2.errno != 2:
                raise
            return None
    return tuple(map(int, version_string.split('.')))

def get_irods_version_from_bash():
    try:
        with open('/var/lib/irods/VERSION') as f:
            for line in f:
                key, _, value = line.rstrip('\n').partition('=')
                if key == 'IRODSVERSION':
                    return tuple(map(int, value.split('.')))
            return None
    except IOError as e:
        if e.errno != 2:
            raise
        return None

# from: https://github.com/ansible/ansible/blob/0a439df4b0a3173868884aa4778fd99ec80b505f/lib/ansible/module_utils/basic.py
def get_distribution():
    ''' return the distribution name '''
    if platform.system() == 'Linux':
        try:
            supported_dists = platform._supported_dists + ('arch',)
            distribution = platform.linux_distribution(supported_dists=supported_dists)[0].capitalize()
            if not distribution and os.path.isfile('/etc/system-release'):
                distribution = platform.linux_distribution(supported_dists=['system'])[0].capitalize()
                if 'Amazon' in distribution:
                    distribution = 'Amazon'
                else:
                    distribution = 'OtherLinux'
        except:
            # FIXME: MethodMissing, I assume?
            distribution = platform.dist()[0].capitalize()
    else:
        distribution = None
    return distribution

def raise_not_implemented_for_distribution():
    raise NotImplementedError, 'not implemented for distribution [{0}]'.format(get_distribution()), sys.exc_info()[2]

def get_package_dependencies(package_name):
    externals_list = []
    if get_distribution() == 'Centos linux':
        proc = Popen(['rpm', '-qp', package_name, '--requires', '|', 'grep', 'irods-externals'], stdout=PIPE, stderr=PIPE)
        _out, _err = proc.communicate()
        _out_list = _out.split('\n')
        for _str in _out_list:
            if 'irods-externals' in _str:
                _str = _str.strip() + '*'
                externals_list.append(_str)
    elif get_distribution() == 'Ubuntu':
        proc = Popen(['dpkg', '-I', package_name], stdout=PIPE, stderr=PIPE)
        _out, _err = proc.communicate()
        _out_list = _out.split('\n')
        for _str in _out_list:
            if 'irods-externals' in _str:
                dependency_list = _str.split(':')[1].split(',')
                for dependency in dependency_list:
                    if 'irods-externals' in dependency:
                        dependency = dependency.strip() + '*'
                        externals_list.append(dependency)
    else:
        print(get_distribution(), ' distribution not supported')

    return ','.join(externals_list)

def install_externals_from_list(externals_list, externals_dir):
    install_externals_cmd = 'python install_externals.py --externals_root_directory {0} --externals_to_install {1}'.format(externals_dir, externals_list)
    subprocess.check_call(install_externals_cmd, shell=True)

def install_irods_repository_apt():
    subprocess_get_output('wget -qO - https://core-dev.irods.org/irods-core-dev-signing-key.asc | sudo apt-key add -', shell=True, check_rc=True)
    subprocess_get_output('echo "deb [arch=amd64] https://core-dev.irods.org/apt/ $(lsb_release -sc) main" | sudo tee /etc/apt/sources.list.d/renci-irods-core-dev.list', shell=True, check_rc=True)
    subprocess.check_call('apt-get clean && apt-get update', shell=True)

def install_irods_repository_yum():
    subprocess_get_output(['sudo', 'rpm', '--import', 'https://core-dev.irods.org/irods-core-dev-signing-key.asc'], check_rc=True)
    subprocess_get_output('wget -qO - https://core-dev.irods.org/renci-irods-core-dev.yum.repo | sudo tee /etc/yum.repos.d/renci-irods-core-dev.yum.repo', shell=True, check_rc=True)

def install_irods_repository_zypper():
    subprocess_get_output(['sudo', 'rpm', '--import', 'https://core-dev.irods.org/irods-core-dev-signing-key.asc'], check_rc=True)
    subprocess_get_output('wget -qO - https://core-dev.irods.org/renci-irods-core-dev.zypp.repo | sudo tee /etc/zypp/repos.d/renci-irods-core-dev.zypp.repo', shell=True, check_rc=True)

def install_irods_repository():
    dispatch_map = {
        'Ubuntu': install_irods_repository_apt,
        'Centos': install_irods_repository_yum,
        'Centos linux': install_irods_repository_yum,
        'Opensuse ': install_irods_repository_zypper,
    }

    try:
        return dispatch_map[get_distribution()]()
    except KeyError:
        raise_not_implemented_for_distribution()

def install_os_packages_apt(packages):
    subprocess_get_output(['sudo', 'apt-get', 'clean'], check_rc=True)
    subprocess_get_output(['sudo', 'apt-get', 'update'], check_rc=True)
    args = ['sudo', 'apt-get', 'install', '-y'] + list(packages)
    subprocess_get_output(args, check_rc=True)

def install_os_packages_yum(packages):
    args = ['sudo', 'yum', 'install', '-y'] + list(packages)
    subprocess_get_output(args, check_rc=True)

def install_os_packages_zypper(packages):
    args = ['sudo', 'zypper', '--non-interactive', 'install'] + list(packages)
    subprocess_get_output(args, check_rc=True)

def install_os_packages(packages):
    dispatch_map = {
        'Ubuntu': install_os_packages_apt,
        'Centos': install_os_packages_yum,
        'Centos linux': install_os_packages_yum,
        'Opensuse ': install_os_packages_zypper,
    }
    try:
        dispatch_map[get_distribution()](packages)
    except KeyError:
        raise_not_implemented_for_distribution()

def install_os_packages_from_files_apt(files):
    '''files are installed individually in the order supplied, so inter-file dependencies must be handled by the caller'''
    subprocess_get_output(['sudo', 'apt-get', 'clean'], check_rc=True)
    subprocess_get_output(['sudo', 'apt-get', 'update'], check_rc=True)
    install_os_packages_apt(['gdebi'])
    for f in files:
        subprocess_get_output(['sudo', 'gdebi', '-n', f], check_rc=True)

def install_os_packages_from_files_yum(files):
    args = ['sudo', 'yum', 'localinstall', '-y', '--nogpgcheck'] + list(files)
    subprocess_get_output(args, check_rc=True)

def install_os_packages_from_files_zypper(files):
    install_os_packages_zypper(files)

def install_os_packages_from_files(files):
    dispatch_map = {
        'Ubuntu': install_os_packages_from_files_apt,
        'Centos': install_os_packages_from_files_yum,
        'Centos linux': install_os_packages_from_files_yum,
        'Opensuse ': install_os_packages_from_files_zypper,
    }
    try:
        dispatch_map[get_distribution()](files)
    except KeyError:
        raise_not_implemented_for_distribution()

def get_munge_external():
    munge_external = 'irods-externals-mungefs*'
    return munge_external

def install_irods_packages(database_type, database_machine, install_externals, irods_packages_directory, externals_directory=None, upgrade=False, is_provider=False):
    setup_database_client = 'python setup_database_client.py --database_type {0}'.format(database_type)
    if upgrade:
        #don't configure the database
        pass
    else:
        if is_provider:
            subprocess.check_call(setup_database_client, shell=True)

    if get_distribution() == 'Centos linux':
        subprocess_get_output(['rpm', '--rebuilddb'], check_rc=True)

    if os.path.exists(irods_packages_directory):
        icat_package_basename = filter(lambda x:'irods-server' in x, os.listdir(irods_packages_directory))[0]
        if 'irods-server' in icat_package_basename:
            server_package = os.path.join(irods_packages_directory, icat_package_basename)
            if install_externals:
                externals_list = get_package_dependencies(server_package)
                externals_list = externals_list + ',' + get_munge_external()
                install_externals_from_list(externals_list, externals_directory)
            else:
                install_irods_repository()
                munge_external = get_munge_external()
                install_os_packages([munge_external])
                #need to install munge here too after munge in core dev

            runtime_package = server_package.replace('irods-server', 'irods-runtime')
            icommands_package = server_package.replace('irods-server', 'irods-icommands')
            database_plugin = get_database_plugin(irods_packages_directory, database_type)
            install_os_packages([runtime_package, icommands_package, server_package, database_plugin])
        else:
            raise RuntimeError('unhandled package name')

def get_database_plugin(irods_packages_directory, database_type):
    if database_type == 'mariadb':
        database_type = 'mysql'

    package_filter = 'irods-database-plugin-' + database_type
    database_plugin_basename = filter(lambda x:package_filter in x, os.listdir(irods_packages_directory))[0]
    database_plugin = os.path.join(irods_packages_directory, database_plugin_basename)
    return database_plugin

def setup_irods(database_type, database_machine=None):
    if database_type == 'postgres':
        subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input'], shell=True)
    elif database_type == 'mysql':
        subprocess.check_call(['python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_mysql.input'], shell=True)
    elif database_type == 'oracle':
        status = 'running'
        while status == 'running':
            status_cmd = ['docker', 'inspect', '--format', '{{.State.Health.Status}}', database_machine]
            status_proc = Popen(status_cmd, stdout = PIPE, stderr=PIPE)
            _out, _err = status_proc.communicate()
            if 'healthy' in _out:
                status = _out

            time.sleep(1)

        subprocess.check_call(['export LD_LIBRARY_PATH=/usr/lib/oracle/11.2/client64/lib:$LD_LIBRARY_PATH; export ORACLE_HOME=/usr/lib/oracle/11.2/client64; export PATH=$ORACLE_HOME/bin:$PATH; python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_oracle.input'], shell=True)
    else:
        print(database_type, ' not supported')

def upgrade(upgrade_packages_directory, database_type, install_externals, externals_directory=None, is_provider=True):
    initial_version = get_irods_version()
    stop_server(initial_version)
    #upgrade packages
    install_irods_packages(database_type, install_externals, upgrade_packages_directory, externals_directory, upgrade = True, is_provider = is_provider)
    final_version = get_irods_version()
    upgrade_core_re(initial_version, final_version)
    stop_server(final_version)
    start_server(final_version)

def stop_server(irods_version):
    if irods_version <= (4,1):
        subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/iRODS/irodsctl stop'], check_rc=True)
    else:
        subprocess_get_output(['su', '-', 'irods', '-c', '/var/lib/irods/irodsctl stop'], check_rc=True)

def upgrade_core_re(initial_version, final_version):
    if initial_version < (4,1) and final_version >= (4,1):

        contents = '''
acDeleteUserZoneCollections {
  acDeleteCollByAdminIfPresent("/"++$rodsZoneProxy++"/home",$otherUserName);
  acDeleteCollByAdminIfPresent("/"++$rodsZoneProxy++"/trash/home",$otherUserName);
}
acDeleteCollByAdminIfPresent(*parColl,*childColl) {
  *status=errorcode(msiDeleteCollByAdmin(*parColl,*childColl));
  if(*status!=0 && *status!=-808000) {
    failmsg(*status, "msiDeleteCollByAdmin failed in acDeleteCollByAdminIfPresent")
  }
}
'''
        with tempfile.NamedTemporaryFile(prefix='core.re.prepend') as f:
            f.write(contents)
            f.flush()
            subprocess_get_output(['sudo', 'su', '-', '-c', 'cat {0} /etc/irods/core.re > /etc/irods/core.re.updated'.format(f.name)], check_rc=True)
            subprocess_get_output(['sudo', 'su', '-', '-c', 'mv /etc/irods/core.re.updated /etc/irods/core.re'], check_rc=True)
            subprocess_get_output(['sudo', 'chown', 'irods:irods', '/etc/irods/core.re'], check_rc=True)

def start_server(irods_version):
    if irods_version <= (4,1):
        subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', '/var/lib/irods/iRODS/irodsctl start'], check_rc=True)
    else:
        subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', '/var/lib/irods/irodsctl start'], check_rc=True)

def subprocess_get_output(*args, **kwargs):
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    check_rc = False
    if 'check_rc' in kwargs:
        check_rc = kwargs['check_rc']
        del kwargs['check_rc']
    data = None
    if 'data' in kwargs:
        data = kwargs['data']
        del kwargs['data']
    p = subprocess.Popen(*args, **kwargs)
    out, err = p.communicate(data)
    if check_rc:
        if p.returncode != 0:
            raise RuntimeError('''subprocess_get_output() failed
args: {0}
kwargs: {1}
returncode: {2}
stdout: {3}
stderr: {4}
'''.format(args, kwargs, p.returncode, out, err))
    return p.returncode, out, err
