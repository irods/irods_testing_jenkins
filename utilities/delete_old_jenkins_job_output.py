import datetime
import os
import shutil

super_dir = '/projects/irods/vsphere-testing/jenkins-job-output'
date_cutoff = datetime.datetime.now() - datetime.timedelta(days=40)


def delete_old_directory(directory_full_path):
    if directory_full_path != os.path.abspath(directory_full_path):
        raise RuntimeError('delete_old_directory only works on full paths')
    if os.path.islink(directory_full_path):
        raise RuntimeError('delete_old_directory does not work on symlinks')
    if not os.path.isdir(directory_full_path):
        raise RuntimeError('delete_old_directory only works on directories')

    st = os.stat(directory_full_path)
    t = st.st_mtime
    date = datetime.datetime.fromtimestamp(t)
    if date < date_cutoff:
        print directory_full_path
        shutil.rmtree(directory_full_path)

if __name__ == '__main__':
    for d0 in os.listdir(super_dir):
        d0_full = os.path.join(super_dir, d0)
        for d1 in os.listdir(d0_full):
            d1_full = os.path.join(d0_full, d1)
            delete_old_directory(d1_full)

