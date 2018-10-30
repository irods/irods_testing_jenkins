from __future__ import print_function

import datetime
import os
import subprocess
import sys


if __name__ == '__main__':
    BACKUP_DIR = '/projects/irods/vsphere-testing/jenkins-backup/jenkins-homes'

    # tar --create --gzip --file jenkins_backup.tar.gz --exclude='jobs/*/builds' --exclude='jobs/*/lastStable' --exclude='jobs/*/lastSuccessful' --exclude='jobs/*/workspace*' --directory /projects/irods/jenkins_home .
    p = subprocess.Popen(['tar', '--create', '--gzip', '--file', os.path.join(BACKUP_DIR, 'jenkins_backup_{}.tar.gz'.format(datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f'))), '--exclude=jobs/*/builds', '--exclude=jobs/*/lastStable', '--exclude=jobs/*/lastSuccessful', '--exclude=jobs/*/workspace*', '--directory', '/projects/irods/jenkins_home', '.'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()

    if p.returncode != 0:
        print(
'''tar failed with exit code {}
stdout:
{}

stderr:
{}
'''.format(p.returncode, stdout, stderr), file=sys.stderr)
