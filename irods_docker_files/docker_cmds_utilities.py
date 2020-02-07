#!/usr/bin/python
from __future__ import print_function

import time
import subprocess
from subprocess import Popen, PIPE


def get_docker_cmd(run_cmd, exec_cmd, stop_cmd, container_name, alias_name, database_container, database_type, network_name, extra_args=None):
    docker_cmd = {'run_cmd': run_cmd,
                  'exec_cmd': exec_cmd,
                  'stop_cmd': stop_cmd,
                  'container_name': container_name,
                  'alias_name': alias_name,
                  'database_container': database_container,
                  'database_type': database_type,
                  'network_name': network_name
                 }
    if extra_args is not None:
        docker_cmd.update(extra_args)

    print(docker_cmd)
    return docker_cmd

def build_irods_zone(build_tag, base_image, database_type, dockerfile='Dockerfile.install_and_test', install_database=True):
    docker_cmd =  ['docker build -t {0} --build-arg base_image={1} -f {2} .'.format(build_tag, base_image, dockerfile)]
    run_build = subprocess.check_call(docker_cmd, shell = True)
    if install_database:
        if database_type == 'oracle':
            docker_cmd = ['docker build -t {0} -f Dockerfile.xe .'.format('oracle/database:11.2.0.2-xe')]
            run_build = subprocess.check_call(docker_cmd, shell = True)
        else:
            import configuration
            database_image = configuration.database_dict[database_type]
            pull_image = ['docker pull {0}'.format(database_image)]
            subprocess.check_call(pull_image, shell=True)

def create_network(network_name):
    check_network = Popen(['docker', 'network', 'ls'], stdout=PIPE, stderr=PIPE)
    _out, _err = check_network.communicate()
    if not network_name in _out:
        docker_cmd = ['docker', 'network', 'create', '--attachable', network_name]
        network = subprocess.check_call(docker_cmd)

def connect_to_network(machine_name, alias_name, network_name):
    network_cmd = ['docker', 'network', 'connect', '--alias', alias_name, network_name, machine_name]
    proc = Popen(network_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = proc.communicate()

def delete_network(network_name):
    while True:
        rm_network = Popen(['docker', 'network', 'rm', network_name], stdout=PIPE, stderr=PIPE)
        _nout, _nerr = rm_network.communicate()
        if 'error' not in _nerr:
            break
        time.sleep(1)

def is_container_running(container_name):
    _running = False
    state_cmd = ['docker', 'inspect', '-f', '{{.State.Running}}', container_name]
    while not _running:
        state_proc = Popen(state_cmd, stdout=PIPE, stderr=PIPE)
        _sout, _serr = state_proc.communicate()
        if 'true' in _sout:
            _running = True
        time.sleep(1)
    return _running

def check_container_health(container_name):
    while True:
        status_cmd = ['docker', 'inspect', '--format', '{{.State.Health.Status}}', container_name]
        status_proc = Popen(status_cmd, stdout = PIPE, stderr=PIPE)
        _out, _err = status_proc.communicate()
        if 'healthy' in _out:
            break
        time.sleep(1)

def create_federation_args(remote_zone):
    remote_version_cmd = ['docker', 'exec', remote_zone, 'python', 'get_irods_version.py']
    remote_irods_version = None
    while remote_irods_version == None:
        proc = subprocess.Popen(remote_version_cmd, stdout = PIPE, stderr = PIPE)
        _out, _err = proc.communicate()
        if _out is not None or _out != 'None':
            remote_irods_version = _out
        time.sleep(1)

    irods_version = remote_irods_version.split('\n')[0].split('(')[1].split(')')[0].replace(', ','.')
    federation_args = ' '.join([irods_version, 'tempZone', 'icat.tempZone.example.org'])
    return federation_args

def run_command_in_container(run_cmd, exec_cmd, stop_cmd, irods_container, alias_name, database_container, database_type, network_name, **kwargs):
    # the docker run command (stand up a container)
    print(kwargs)
    run_proc = Popen(run_cmd, stdout=PIPE, stderr=PIPE)
    _out, _err = run_proc.communicate()
    if database_container is not None:
        if not 'otherZone' in alias_name:
            create_network(network_name)
        _icat_running = is_container_running(irods_container)
        if _icat_running:
            connect_to_network(irods_container, alias_name, network_name)

        if not 'resource' in alias_name:
            database_alias = 'database.example.org'
            if database_type == 'oracle':
                database_alias = 'oracle.example.org'
                run_cmd = ['docker', 'run', '-d', '--rm',  '--name', database_container, '--shm-size=1g', '-e', 'ORACLE_PWD=testpassword', 'oracle/database:11.2.0.2-xe']
            else:
                import configuration

                database_image = configuration.database_dict[database_type]
                run_cmd = ['docker', 'run', '-d', '--rm',  '--name', database_container]
                if database_type == 'postgres':
                    database_alias = 'postgres.example.org'
                    if 'otherZone' in alias_name:
                        database_alias = 'postgres.otherZone.example.org'
                    passwd_env_var = 'POSTGRES_PASSWORD=testpassword'
                elif database_type == 'mysql' or database_type == 'mariadb':
                    database_alias = 'mysql.example.org'
                    if 'otherZone' in alias_name:
                        database_alias = 'postgres.otherZone.example.org'
                    passwd_env_var = 'MYSQL_ROOT_PASSWORD=password'
                    run_cmd.extend(['-e', 'MYSQL_DATABASE=ICAT', '-e', 'MYSQL_USER=irods', '-e', 'MYSQL_PASSWORD=testpassword'])

                run_cmd.extend(['-e', passwd_env_var, '-h', database_alias, database_image])
                print('database_run_cmd --> ', run_cmd)

            run_proc = Popen(run_cmd, stdout=PIPE, stderr=PIPE)
            _out, _err = run_proc.communicate()
            _running = is_container_running(database_container)
            if _running:
                connect_to_network(database_container, database_alias, network_name)
                if not database_type == 'oracle':
                    setup_database = 'python setup_database.py --database_type {0} --database_machine {1} --provider_machine {2} --network_name {3}'.format(database_type, database_container, irods_container, network_name)
                    subprocess.check_call(setup_database, shell=True)
                else:
                    check_container_health(database_container)

    # execute a command in the running container
    exec_proc = Popen(exec_cmd, stdout=PIPE, stderr=PIPE)
    _eout, _eerr = exec_proc.communicate()
    _exec_rc = exec_proc.returncode
    if _exec_rc == 0 and 'otherZone' in alias_name:
        federation_args = create_federation_args(kwargs['remote_zone'])
        print(federation_args)
        test_type = kwargs['test_type']
        test_name = kwargs['test_name']

        run_test_cmd = ['docker', 'exec', irods_container, 'python', 'run_tests_in_zone.py', '--test_type', test_type, '--specific_test', test_name, '--federation_args', federation_args]
        print('run test cmd', run_test_cmd)
        run_test_proc = Popen(run_test_cmd, stdout=PIPE, stderr=PIPE)
        _eout, _eerr = run_test_proc.communicate()
        _rc = run_test_proc.returncode

    # stop the container
    Popen(stop_cmd).wait()
    if database_container is not None:
        database_stop = ['docker', 'stop', database_container]
        Popen(database_stop).wait()
        delete_network(network_name)

    return _exec_rc
