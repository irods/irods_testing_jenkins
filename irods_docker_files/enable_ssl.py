#!/usr/bin/python
from __future__ import print_function
from subprocess import Popen, PIPE

import argparse
import json
import os
import subprocess
import tempfile
import time

rsa_keyfile_path = '/etc/irods/server.key'
ssl_certificate_path = '/etc/irods/server.crt'
diffie_hellman_parameters_path = '/etc/irods/dhparams.pem'

def enable_ssl(machine_type = None, machine_list = None):
    if machine_type == None:
        install_ssl_files(machine_list)
    else:
        change_permissions()    
        update_irods_environment()
        update_core_re()

def install_ssl_files(machine_list):
    with tempfile.NamedTemporaryFile(prefix='rsa-keyfile', delete=False) as f_rsa_keyfile:
        create_rsa_keyfile(f_rsa_keyfile.name)
        with tempfile.NamedTemporaryFile(prefix='self-signed-certificate') as f_self_signed_certificate:
            create_self_signed_certificate(f_rsa_keyfile.name, f_self_signed_certificate.name)
            with tempfile.NamedTemporaryFile(prefix='diffie-hellman-parameters') as f_diffie_hellman_parameters:
                create_diffie_hellman_parameters(f_diffie_hellman_parameters.name)

                files_to_copy = [(f_rsa_keyfile.name, '/ssl_keys/server.key', '0600'),
                                 (f_self_signed_certificate.name, '/ssl_keys/server.crt', '0666'),
                                 (f_diffie_hellman_parameters.name, '/ssl_keys/dhparams.pem', '0600')]
                for src, dst, perms in files_to_copy:
                    copy_file_to_machines(machine_list, src, dst)
     
def copy_file_to_machines(machine_list, src, dst):
    if machine_list is not None:
        for machine in machine_list.split(' '):
            print(machine)
            print(src, ' --- ', dst)
            print(os.path.exists(src))
            copy_cmd = "docker exec -i {0} sh -c 'cat > '{1}'' < {2}".format(machine, dst, src)
            print(copy_cmd)
            copy_proc = subprocess.check_call(copy_cmd, shell=True)

def change_permissions():
    files_to_copy = [('/ssl_keys/server.key', rsa_keyfile_path, '0600'),
                     ('/ssl_keys/server.crt', ssl_certificate_path, '0666'),
                     ('/ssl_keys/dhparams.pem', diffie_hellman_parameters_path, '0600')]
    
    for src, dst, perms in files_to_copy:
        path_exists = False
        while not path_exists:
            if os.path.exists(src):
                subprocess.check_call(['cp', src, dst])
                subprocess.check_call(['chown', 'irods:irods', dst])
                subprocess.check_call(['chmod', perms, dst])
                path_exists = True
            else:
                time.sleep(1)

def create_rsa_keyfile(filename):
    subprocess.check_call(['openssl', 'genrsa', '-out', filename])

def create_self_signed_certificate(filename_key, filename_certificate):
    p = Popen(['openssl', 'req', '-new', '-x509', '-key', filename_key, '-out', filename_certificate, '-days', '365'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate('\n'*7)
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args, 'stdout [{0}], stderr [{1}]'.format(out, err))

def create_diffie_hellman_parameters(filename):
    subprocess.check_call(['openssl', 'dhparam', '-2', '-out', filename, '1024'])

def update_irods_environment():
    filename = '/var/lib/irods/.irods/irods_environment.json'
    update_dict = {
        'irods_ssl_certificate_key_file': rsa_keyfile_path,
        'irods_ssl_certificate_chain_file': ssl_certificate_path,
        'irods_ssl_dh_params_file': diffie_hellman_parameters_path,
        'irods_client_server_policy': 'CS_NEG_REQUIRE',
        'irods_ssl_verify_server': 'cert',
        'irods_ssl_ca_certificate_file': ssl_certificate_path,
    }
    with open(filename) as f:
        dct = json.load(f)
    dct.update(update_dict)
    with open(filename, 'w') as f:
        json.dump(dct, f, indent=4, sort_keys=True)

def update_core_re():
    import fileinput
    import re
    
    for line in fileinput.FileInput("/etc/irods/core.re", inplace=1, backup='.bak'):
        line = re.sub(r'^acPreConnect\(\*OUT\) \{ \*OUT="CS_NEG_(DONT_CARE|REFUSE)"; \}$', 'acPreConnect(*OUT) { *OUT="CS_NEG_REQUIRE"; }', line.rstrip())
        print(line)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Enable SSL for iRODS topology tests')
    parser.add_argument('--machine_type', type=str)
    parser.add_argument('--machine_list', type=str)
    args = parser.parse_args()

    enable_ssl(args.machine_type, args.machine_list)
