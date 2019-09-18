#!/usr/bin/python

from __future__ import print_function

import configuration
import argparse
import subprocess
import sys

from github import Github

if sys.version_info < (3, 0):
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

# Dereference commitish (branch name, SHA, partial SHA, etc.) to a full SHA
def get_sha_from_commitish(_repo, _commitish):
    try:
        repo = urlparse(_repo).path.strip('/')
        return Github().get_repo(repo).get_commit(_commitish).sha
    except:
        print("Error getting SHA from repo [{0}] for commitish [{1}]. Please make sure URL and commitish are correct.".format(_repo, _commitish))
        print(sys.exc_info()[0], ': ', sys.exc_info()[1])
        return _commitish

def build_irods_in_containers(base_os, build_id, irods_repo, irods_commitish, icommands_repo, icommands_commitish, output_directory):
    build_tag = base_os +'-irods-build:' + build_id
    print(build_tag)
    base_image = base_os + ':' + build_id 

    # If SHA was built previously, cached build image will be used.
    irods_sha = get_sha_from_commitish(irods_repo, irods_commitish)
    icommands_sha = get_sha_from_commitish(icommands_repo, icommands_commitish)

    docker_cmd = ['docker build -t {0} --build-arg base_image={1} --build-arg arg_irods_repo={2} --build-arg arg_irods_commitish={3} --build-arg arg_icommands_repo={4} --build-arg arg_icommands_commitish={5} -f Dockerfile.build_irods .'.format(build_tag, base_image, irods_repo, irods_sha, icommands_repo, icommands_sha)]
    print(docker_cmd)
    run_build = subprocess.check_call(docker_cmd, shell=True)
    save_irods_build(build_tag, output_directory)

def save_irods_build(image_name, output_directory):
    save_cmd = ['docker run --rm -v {0}:/jenkins_output {1}'.format(output_directory, image_name)] 
    save_build = subprocess.check_call(save_cmd, shell=True)

def main():
    parser = argparse.ArgumentParser(description='Build irods in base os-containers')
    parser.add_argument('-p', '--platform_target', type=str, required=True)
    parser.add_argument('-b', '--build_id', type=str, required=True)
    parser.add_argument('--irods_repo', type=str, required=True)
    parser.add_argument('--irods_commitish', type=str, required=True)
    parser.add_argument('--icommands_repo', type = str, required=True)
    parser.add_argument('--icommands_commitish', type=str, required=True)
    parser.add_argument('-o', '--output_directory', type=str, required=True)

    args = parser.parse_args()
    print(args.irods_repo)
    print(args.irods_commitish)
    print(args.icommands_repo)
    print(args.icommands_commitish)
    build_irods_in_containers(args.platform_target, args.build_id, args.irods_repo, args.irods_commitish, args.icommands_repo, args.icommands_commitish, args.output_directory)
   
if __name__ == '__main__':
    main()

