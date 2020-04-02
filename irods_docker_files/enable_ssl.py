#!/usr/bin/python
from __future__ import print_function

import argparse
import json
import os
import shutil
import tempfile
import time
from pwd import getpwnam
from grp import getgrnam

rsa_keyfile_path = '/etc/irods/server.key'
ssl_certificate_path = '/etc/irods/server.crt'
diffie_hellman_parameters_path = '/etc/irods/dhparams.pem'

def enable_ssl():
    change_permissions()
    update_irods_environment()
    update_core_re()

def change_permissions():
    files_to_copy = [('/ssl_keys/server.key', rsa_keyfile_path, 0o600),
                     ('/ssl_keys/server.crt', ssl_certificate_path, 0o666),
                     ('/ssl_keys/dhparams.pem', diffie_hellman_parameters_path, 0o600)]
    for src, dst, perms in files_to_copy:
        shutil.copy(src, dst)
        uid = getpwnam('irods').pw_uid
        gid = getgrnam('irods').gr_gid
        os.chown(dst, uid, gid)
        os.chmod(dst, perms)

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
    enable_ssl()
