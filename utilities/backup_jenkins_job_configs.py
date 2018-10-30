from __future__ import print_function

import datetime
import os
import shutil

CONFIG_DIR = '/projects/irods/jenkins_home/jobs'
BACKUP_ROOT_DIR = '/projects/irods/vsphere-testing/jenkins-backup/job-configs'

BACKUP_DIR = os.path.join(BACKUP_ROOT_DIR, datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f'))
os.mkdir(os.path.join(BACKUP_DIR))

for i in os.listdir(CONFIG_DIR):
    source_dir = os.path.join(CONFIG_DIR, i)
    if os.path.isdir(source_dir):
        target_dir = os.path.join(BACKUP_DIR, i)
        os.mkdir(target_dir)
        def copy_file_from_source_to_target(filename):
            source_filename = os.path.join(source_dir, filename)
            print('{0} -> {1}'.format(source_filename, target_dir))
            shutil.copy2(source_filename, target_dir)
        copy_file_from_source_to_target('config.xml')
        copy_file_from_source_to_target('nextBuildNumber')

