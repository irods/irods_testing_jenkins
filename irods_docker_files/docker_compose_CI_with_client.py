#!/usr/bin/env python3

from __future__ import print_function
import argparse
import subprocess
import threading
import os
import re
import sys
import copy
import json
import time

from os.path import join
import compose.cli.command

from docker_compose_ci_util import (testgen, readgen,
                                    run_build_containers,
                                    get_ordered_dependencies)

# -------------------------------- Test code

def test():
    import io
    f = testgen(
        io.BytesIO(b'abc\ndef\nghij') ## or: #'/tmp/test.dat'
        ,tm=0
    )
    print_generated = readgen([sys.stdout])
    print_generated(f,
        ident_ = 'mhyident'
    )



def main() :

    parser = argparse.ArgumentParser()

    parser.add_argument('-r','--remote_repository', action='store', dest='remote_repository', required=True,
                             help='Name a remote repository to clone')

    parser.add_argument('-l','--local_repository', action='store', dest='local_repository', required=True,
                             help='Name of local/cloned repository in which to run')

    parser.add_argument('-j','--json_config', action='store', dest='json_config', default='{}',
                             help='''JSON dictionary to guide building and running tests''')

    parser.add_argument('-c','--commitish', action='store', dest='commitish', required = True,
                             help='')

    parser.add_argument('--dry_run', action='store_true', dest='dry_run', default = '',
                             help='')

    Args = parser.parse_args()

    modifiers_for_config = json.loads(Args.json_config)

    if Args.dry_run:
      print(json.dumps(modifiers_for_config,indent=4))
      exit(126)

    subprocess.check_output(['git', 'clone', '--recurse-submodules', '-q',
                             Args.remote_repository, Args.local_repository ])

    subprocess.check_output(['git', 'checkout', Args.commitish], cwd=Args.local_repository)

    # Find the docker compose project in the cloned client repo,
    #  and import the module that runs the test
    #

    import importlib
    sys.path.insert(0, Args.local_repository)

    # You can modify the python3 command invoking this script from the Jenkins config.xml pipeline section, in
    # order to insert new override KEY=VALUE pairs for modifiers_for_config.
    # For example:
    #
    #    def build_cmd = 'env irods_package_dir="'+IRODS_PACKAGE_DIR+'" ' +  // IRODS_PACKAGE_DIR entry box value
    #                             '    X="' + 'HELLO' + '" ' +               // literal value "HELLO"
    #                             '    DOTENV_INJECT_KEYS=irods_package_dir,X ' +
    #                             ' python3 -u docker_compose_CI_with_client.py ' +
    #                             ' --remote_repo=' + PARAMETER_REMOTE_REPO  +

    entry_box_inject_keys = os.environ.get('DOTENV_INJECT_KEYS','')

    inject_keys = list(filter(None, [k.strip() for k in entry_box_inject_keys.split(',')]))
    if inject_keys:
        dotenv_update_dct = modifiers_for_config.setdefault('yaml_substitutions',{})
        dotenv_update_dct.update( (k,os.environ.get(k,'')) for k in inject_keys)

    test_hook_module = importlib.import_module('irods_consortium_continuous_integration_test_module')

    # The following runs the test_hook module imported from client repo. That module's
    # run() function calls back via an injected object of class 'CI_client_interface'.

    compose_proj_dir = Args.local_repository

    initialize = getattr(test_hook_module,'init',None)
    if callable(initialize):
        dir_ = initialize()
        if dir: compose_proj_dir = dir_

    exit(test_hook_module.run(
        CI_client_interface (modifiers_for_config, compose_proj_dir)
    ))


class CI_client_interface (object):

    def __init__(self, modifier_config, compose_dir, compose_project=None):

        self.modifier_config = modifier_config
        self.config = {}
        self.compose_prj = compose_project
        self.compose_path = os.path.abspath(compose_dir)


    @staticmethod
    def _spawn_container_log_spoolers(containers, streams = ()):
        filelist = [sys.stdout] + list(_ for _ in streams)
        locks = { f: threading.Lock() for f in filelist }
        for ctnr in containers:
            t = threading.Thread( target=readgen(filelist, locks),
                                  args=(ctnr.log_stream, ctnr.name) )
            t.setDaemon(True)
            t.start()


    def run_and_wait_on_client_exit( self,
                                     name_pattern = 'client[-_]runner',
                                     rgx_flags    = re.IGNORECASE,
                                     import_vars  = True ):

        #  Create YAML substitution file (.env) and the container environment files {SERVICE_NAME}.env
        #  for optional inclusion in each docker-compose.yml services stanza under the key "env_file".
        #
        if import_vars:
            self._import_yaml_subs_and_environ_vars( )
        else:
            print ("-- Warning -- supplied config modifier is not used",
                   file = sys.stderr)

        proj = self.compose_prj
        if  proj is None:
            proj = compose.cli.command.get_project( self.compose_path )

        build_order = self.config.get("build_services_in_order")  # should be 'None' if no build/prepare services

        Entire_Project_Built = False
        if build_order is None:
            proj.build()                 # build all services from docker-compose.yml
            Entire_Project_Built = True
        else:
            # build and run named services (to prepare/build for client run)
            # if empty (specified as '' or []) build nothing in the project
            if build_order:
                run_build_containers(proj,
                                     [build_order] if isinstance (build_order,str) else list(build_order))

        #  -- TODO  --
        #  Determine which container to wait on for status code.
        #  Usually "client-runner" or similar
        #  Use "depends_on:" in the docker-compose.yml to specify run dependencies of the main container and thus which
        #    services run in the up() phase.

        main_service = self.config.get("up_service") # is the None object, if name not provided

        if not Entire_Project_Built:
            if not main_service:
                print ("ERROR - A comprehensive docker-compose project build was not performed because build stages were given in the config.")
                print ("        But an 'up_service' name was not given, which could result in running out-of-date services.  Exiting.... ")
                exit(1)
            proj.build( service_names=get_ordered_dependencies(proj,main_service) )

        containers = self.compose_prj = proj.up(service_names = [main_service] if main_service else None)

        # -- Match client container by a default name pattern if not given, else choose by config-provided name
        #
        if main_service:
            status_containers = [ c for c in containers if c.name_without_project.startswith(main_service) ]
        else:
            rgx = re.compile(name_pattern, rgx_flags)
            status_containers = [ c for c in containers if rgx.match(c.name_without_project) ]

        if len(status_containers) != 1:
            raise RuntimeError("Exactly one container can be waited on for CI status, but the"
                               "names of {} containers were matched".format(len(status_containers)))

        os.environ['TERM'] = 'unknown'
        self._spawn_container_log_spoolers(containers)
        status_code = status_containers[0].wait()

        proj_down_setting = self.config.get("project_down_when_client_exits", False)
        print("DWM ::: proj_down_setting = ", proj_down_setting )
        if proj_down_setting:
            proj.down(remove_image_type = False, include_volumes = True)

        return status_code


    def _import_yaml_subs_and_environ_vars(self):

        yaml_subs = self.config.get("yaml_substitutions",{})
        with open (join(self.compose_path,".env"),"a") as dotEnv_file:
            for k,v in yaml_subs.items():
                dotEnv_file.write("{k}={v}\n".format(**locals()))

        environments = self.config.get("container_environments",{})
        for container_name,env_lookup in environments.items():
            with open(join(self.compose_path, container_name+".env"),"a") as containerEnvironment_File:
                for k,v in env_lookup.items():
                    containerEnvironment_File.write("{k}={v}\n".format(**locals()))


    def store_config(self, basic_config, allow_override = True ):
        self.config = copy.deepcopy(basic_config)
        def update_lhs_scalars_with_rhs (lhs, rhs, keys=()):
            key_hierarchy = lambda newkey: list(keys)+[newkey]
            for k,v in rhs.items():
                v_lhs = lhs.get(k,None)
                if v_lhs is None or type(v) is type(v_lhs): #-- allow update when same types or lacking in LHS
                    if v_lhs is not None and type(v) is dict: #-- recurse if LHS key exists and was has 'dict' type
                        update_lhs_scalars_with_rhs( lhs[k] , rhs[k], key_hierarchy(k) )
                    else:
                        lhs [k] = rhs [k]
                else:
                    print("\n-- WARNING -- not modifying configuration value at level {!r} in key hierarchy"
                          "\ndue to mismatch of value type in basic and modifier configs"
                          "" .format(key_hierarchy(k)), file = sys.stderr)

        if allow_override:
            update_lhs_scalars_with_rhs( self.config, self.modifier_config )
        return self.config.copy()

if __name__ == '__main__':
    if sys.argv[1:] == ['-test']:
        test()
        p = compose.cli.command.get_project('.')
    else:
        main()
