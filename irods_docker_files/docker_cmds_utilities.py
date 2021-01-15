#!/usr/bin/python
from __future__ import print_function

import time
import tempfile
import os
import subprocess
from subprocess import Popen, PIPE

import ci_utilities

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
        docker_cmd.update( extra_args )

    return docker_cmd

def build_irods_zone(build_tag, base_image, database_type, dockerfile='Dockerfile.install_and_test', install_database=True):
    docker_cmd =  ['docker', 'build', '-t', build_tag, '--build-arg', 'base_image={0}'.format(base_image), '-f', dockerfile, '--no-cache', '.']
    ec, out, err = ci_utilities.subprocess_get_output(docker_cmd)
    print('''
DOCKER BUILD OUTPUT FOR "{0}":
    ERROR CODE = {1}
    STDOUT     = {2}
    STDERR     = {3}
'''.format(docker_cmd, ec, out, err))
    if ec != 0:
        raise RuntimeError('"{0}" failed.'.format(docker_cmd))
    if install_database:
        import configuration
        database_image = configuration.database_dict[database_type]
        image_exists = ['docker', 'images', '-q', database_image]
        _out, _err = Popen(image_exists, stdout=PIPE, stderr=PIPE).communicate()
        if _out == '':
            if database_type == 'oracle':
                docker_cmd = ['docker build -t {0} -f Dockerfile.xe .'.format(database_image)]
                run_build = subprocess.check_call(docker_cmd, shell = True)
            else:
                pull_image = ['docker pull {0}'.format(database_image)]
                subprocess.check_call(pull_image, shell=True)

def create_network(network_name):
    check_network = Popen(['docker', 'network', 'ls'], stdout=PIPE, stderr=PIPE)
    out, _ = check_network.communicate()
    if not network_name in out:
        docker_cmd = ['docker', 'network', 'create', '--attachable', network_name]
        network = subprocess.check_call(docker_cmd)

def connect_to_network(machine_name, alias_name, network_name):
    subprocess.check_call(['docker', 'network', 'connect', '--alias', alias_name, network_name, machine_name])

def delete_network(network_name):
    while True:
        p = Popen(['docker', 'network', 'rm', network_name], stdout=PIPE, stderr=PIPE)
        _, err = p.communicate()
        if 'error' not in err:
            break
        time.sleep(1)

def is_container_running(container_name):
    running = False
    state_cmd = ['docker', 'inspect', '-f', '{{.State.Running}}', container_name]
    while not running:
        p = Popen(state_cmd, stdout=PIPE, stderr=PIPE)
        out, _ = p.communicate()
        if 'true' in out:
            running = True
        time.sleep(1)
    return running

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

def install_ssl_files(machine_list):
    with tempfile.NamedTemporaryFile(prefix='rsa-keyfile') as f_rsa_keyfile:
        create_rsa_keyfile(f_rsa_keyfile.name)
        with tempfile.NamedTemporaryFile(prefix='self-signed-certificate') as f_self_signed_certificate:
            create_self_signed_certificate(f_rsa_keyfile.name, f_self_signed_certificate.name)
            with tempfile.NamedTemporaryFile(prefix='diffie-hellman-parameters') as f_diffie_hellman_parameters:
                create_diffie_hellman_parameters(f_diffie_hellman_parameters.name)

                files_to_copy = [(f_rsa_keyfile.name, '/ssl_keys/server.key'),
                                 (f_self_signed_certificate.name, '/ssl_keys/server.crt'),
                                 (f_diffie_hellman_parameters.name, '/ssl_keys/dhparams.pem')]
                for src, dst in files_to_copy:
                    copy_file_to_machines(machine_list, src, dst)

def copy_file_to_machines(machine_list, src, dst):
    if machine_list is not None:
        for machine in machine_list.split(' '):
            print('copying [{0}] (exists:{1}) to dst [{2}] on container [{3}]'.format(str(src), str(os.path.exists(src)), str(dst), str(machine)))
            copy_cmd = "docker cp {0} {1}:{2}".format(src, machine, dst)
            running = is_container_running(machine)
            if running:
                print(copy_cmd)
                copy_proc = subprocess.check_call(copy_cmd, shell=True)

def create_rsa_keyfile(filename):
    subprocess.check_call(['openssl', 'genrsa', '-out', filename])

def create_self_signed_certificate(filename_key, filename_certificate):
    p = Popen(['openssl', 'req', '-new', '-x509', '-key', filename_key, '-out', filename_certificate, '-days', '365'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate('\n'*7)
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args, 'stdout [{0}], stderr [{1}]'.format(out, err))

def create_diffie_hellman_parameters(filename):
    subprocess.check_call(['openssl', 'dhparam', '-2', '-out', filename, '1024'])

def run_database(database_type, database_container, alias_name, network_name):
    database_alias = 'database.example.org'
    import configuration
    database_image = configuration.database_dict[database_type]

    if database_type == 'oracle':
        database_alias = 'oracle.example.org'
        run_cmd = ['docker', 'run', '-d', '--rm',  '--name', database_container, '-h', database_alias, '--shm-size=1g', '-e', 'ORACLE_PWD=testpassword', database_image]
        print('database_run_cmd --> ', run_cmd)
    else:
        run_cmd = ['docker', 'run', '-d', '--rm',  '--name', database_container]
        if database_type == 'postgres':
            database_alias = 'postgres.example.org'
            if 'otherZone' in alias_name:
                database_alias = 'postgres.otherZone.example.org'
            passwd_env_var = 'POSTGRES_PASSWORD=testpassword'
        elif database_type == 'mysql' or database_type == 'mariadb':
            database_alias = 'mysql.example.org'
            if 'otherZone' in alias_name:
                database_alias = 'mysql.otherZone.example.org'
            passwd_env_var = 'MYSQL_ROOT_PASSWORD=password'
            run_cmd.extend(['-e', 'MYSQL_DATABASE=ICAT', '-e', 'MYSQL_USER=irods', '-e', 'MYSQL_PASSWORD=testpassword'])
        run_cmd.extend(['-e', passwd_env_var, '-h', database_alias, database_image])
        print('database_run_cmd --> ', run_cmd)

    Popen(run_cmd, stdout=PIPE, stderr=PIPE).communicate()
    if is_container_running(database_container):
        connect_to_network(database_container, database_alias, network_name)

def execute_shell_command(_cmd, _log):
    _log.write('Executing command: {0}\n'.format(_cmd))

    p = Popen(_cmd, stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()

    _log.write('Error Code: {0}\n'.format(str(p.returncode)))
    if out: _log.write(out)
    if err: _log.write(err)

    _log.write('\n')

    return p.returncode

def run_command_in_container(run_cmd, exec_cmd, stop_cmd, irods_container, alias_name, database_container, database_type, network_name, **kwargs):
    with open(kwargs['log_path'], 'w') as job_log:
        # Launch container for test.
        ec = execute_shell_command(run_cmd, job_log)
        if ec != 0:
           return ec

        if database_container is not None:
            if 'test_type' in kwargs:
                if kwargs['test_type'] == 'standalone_icat':
                    create_network(network_name)
                    run_database(database_type, database_container, alias_name, network_name)

                if 'topology' in kwargs['test_type'] and 'machine_list' in kwargs and kwargs['use_ssl'] is True and alias_name == 'icat.example.org':
                    install_ssl_files(kwargs['machine_list'])

            if is_container_running(irods_container):
                connect_to_network(irods_container, alias_name, network_name)

            if not 'resource' in alias_name:
                if is_container_running(database_container):
                    if database_type == 'oracle':
                        check_container_health(database_container)
                    else:
                        setup_database = 'python setup_database.py --database_type {0} --database_machine {1} --provider_machine {2} --network_name {3}'.format(database_type, database_container, irods_container, network_name)
                        subprocess.check_call(setup_database, shell=True)

        # Execute a command in the running container
        ec = execute_shell_command(exec_cmd, job_log)
        if ec != 0:
            return ec

        # Launch federation test.
        if ec == 0 and 'otherZone' in alias_name:
            federation_args = create_federation_args(kwargs['remote_zone'])
            test_type = kwargs['test_type']
            test_name = kwargs['test_name']

            run_test_cmd = ['docker', 'exec', irods_container, 'python', 'run_tests_in_zone.py', '--test_type', test_type,
                            '--database_type', database_type, '--specific_test', test_name, '--federation_args', federation_args]
            ec = execute_shell_command(run_test_cmd, job_log)
            if ec != 0:
                execute_shell_command(stop_cmd, job_log)
                return ec

        # Stop the container
        job_log.write('Stopping container [' + irods_container + '] ...\n')
        ec = execute_shell_command(stop_cmd, job_log)
        if ec != 0:
            return ec

        if database_container is not None:
            if not 'resource' in alias_name:
                execute_shell_command(['docker', 'stop', database_container], job_log)
                delete_network(network_name)

        return 0

