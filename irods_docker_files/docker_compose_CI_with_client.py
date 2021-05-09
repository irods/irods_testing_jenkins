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
import struct
import base64

from os.path import join, normpath
import compose.cli.command

from docker_compose_ci_util import ( testgen, readgen,
                                     run_build_containers,
                                     get_ordered_dependencies,
                                     set_build_options,
                                     get_build_options
                                   )


# -------------------------------- Local Utility functions

def _ascii_timestamp():
    return base64.b32encode(
             struct.pack('<q', int(time.time()*256))[:5]
           ).decode().lower()

def _without_updir(path, start):
    relative_path = os.path.relpath (path, start = start)
    if [elem for elem in relative_path.split( os.path.sep ) if elem == os.path.pardir]:
        return None
    return relative_path


def _update_lhs_scalars_with_rhs (lhs, rhs, keys=()):
    key_hierarchy = lambda newkey: list(keys)+[newkey]
    for k,v in rhs.items():
        v_lhs = lhs.get(k,None)
        if v_lhs is None or type(v) is type(v_lhs): #-- allow update when same types or lacking in LHS
            if v_lhs is not None and type(v) is dict: #-- recurse if LHS key exists and RHS has 'dict' type
                _update_lhs_scalars_with_rhs( lhs[k] , rhs[k], key_hierarchy(k) )
            else:
                lhs [k] = rhs [k]
        else:
            print("\n-- WARNING -- not modifying configuration value at level {!r} in key hierarchy"
                  "\ndue to mismatch of value type in basic and modifier configs"
                  "" .format(key_hierarchy(k)), file = sys.stderr)


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


# -------------------------------- Reasonable Jenkins defaults

JENKINS_DEFAULTS = {
    'build_options': { 'no_cache': True },
    'project_down_when_client_exits': True,
    'settings_for_project_down' : dict(remove_image_type = True, include_volumes = True)
}

def main() :

    parser = argparse.ArgumentParser()

    parser.add_argument('-r','--remote_repository', action='store', dest='remote_repository', required=True,
                             help='Name a remote repository to clone')

    parser.add_argument('-l','--local_repository', action='store', dest='local_repository', required=True,
                             help='Name of local/cloned repository in which to run')

    parser.add_argument('-p','--preserve_dotenv', action='store_true', dest='preserve_dotenv',
                             help='''preserve an existing .env and append rather than truncating it.''')

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

    project_dir = normpath(Args.local_repository)

    if not os.path.isabs( project_dir ):
        print("""Local repository {project_dir!r} must be absolute, e.g.: /jenkins_sandbox/myproject .""".format(**locals()))
        exit(1)

    if os.path.exists( project_dir ):
        project_dir += "_{}".format(_ascii_timestamp())

    subprocess.check_output(['git', 'clone', '--recurse-submodules', '-q',
                             Args.remote_repository, project_dir ])

    subprocess.check_output(['git', 'checkout', Args.commitish], cwd = project_dir)

    # Find the test hook module in the root of the cloned client repository,

    import importlib
    sys.path.insert(0, project_dir)
    test_hook_module = importlib.import_module('irods_consortium_continuous_integration_test_module')

    ## We can modify the python3 command invoking this script (in the Jenkins config.xml pipeline section), in
    ## order to insert text box entries as KEY=VALUE pairs as overrides in `modifiers_for_config' .
    ## For example:
    #    def build_cmd = 'env irods_package_dir="'+IRODS_PACKAGE_DIR+'" ' +  // Include IRODS_PACKAGE_DIR entry box's text value
    #                             '    X="' + 'HELLO' + '" ' +               //  and variable 'X' having literal value "HELLO"
    #                             '    DOTENV_INJECT_KEYS = irods_package_dir,X ' +
    #                             ' python3 -u docker_compose_CI_with_client.py ' +
    #                             ' --remote_repo=' + PARAMETER_REMOTE_REPO  + // ...

    entry_box_inject_keys = os.environ.get('DOTENV_INJECT_KEYS','')

    inject_keys = list(filter(None, [k.strip() for k in entry_box_inject_keys.split(',')]))
    if inject_keys:
        dotenv_update_dct = modifiers_for_config.setdefault('yaml_substitutions',{})
        dotenv_update_dct.update( (k,os.environ.get(k,'')) for k in inject_keys)

    # Exec the init function if found in the test hook
    #   - The returned string value, if not empty, provides the path containing the docker-compose.yml for test
    #     (Otherwise we default to the root directory for this.)

    option = {}
    initialize = getattr(test_hook_module,'init',None)

    if callable(initialize):
        dir_ = normpath(initialize()) # Allow hint for location of docker-compose project from a possibly relative
        if dir_:                      # path but don't traverse any parent directories of the local repository.
            if not os.path.isabs(dir_):
                dir_ = normpath(join(project_dir, dir_))
            if not _without_updir(dir_, start = project_dir):
                print("""Cannot use project directory {dir_!r} as a parent directory was referenced."""
                      """It is potentially outside of the given local repository {project_dir!r}.""".format(**locals()))
                exit(1)
            if project_dir != dir_: option['project_name'] = os.path.basename(project_dir)
            project_dir = dir_

    # Execute the run function in the client repo's test hook, which typically does the following:
    #   - Sets up with a default configuration.
    #   - Allows the overridie of these default configuration settings with any user-provided ones from Jenkins GUI.
    #   - The injected CI object's run( ) method typically calls run_and_wait_on_client_exit,
    #      which builds and runs services as containers under docker compose.

    exit(test_hook_module.run(
        CI_client_interface (modifiers_for_config, project_dir, preserve_dotenv = Args.preserve_dotenv,
                             jenkins_defaults = JENKINS_DEFAULTS, proj_option = option)
    ))


class CI_client_interface (object):

    def __init__(self, modifier_config, compose_dir, compose_project=None, preserve_dotenv = False,
                 jenkins_defaults = (), proj_option = {}):

        self.modifier_config = modifier_config
        self.config = {}
        self.compose_prj = compose_project
        self.compose_path = os.path.abspath(compose_dir)
        self.preserve_dotenv = preserve_dotenv
        self.proj_option = proj_option
        self.__jenkins_defaults = dict( jenkins_defaults )


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

        Jenkins = self.config.get("jenkins_defaults",{})
        set_build_options( Jenkins.get("build_options",{}) )

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
            proj = compose.cli.command.get_project(self.compose_path , **self.proj_option)

        build_order = self.config.get("build_services_in_order")  # should be 'None' if no build/prepare services

        Entire_Project_Built = False
        if build_order is None:
            proj.build(**get_build_options())   # build all services from docker-compose.yml
            Entire_Project_Built = True
        else:
            # build and run named services (to prepare/build for client run)
            # if empty (specified as '' or []) build nothing in the project
            if build_order:
                run_build_containers(proj,
                                     [build_order] if isinstance (build_order,str) else list(build_order))

        #  The "depends_on:" entries in the docker-compose.yml will help determine run dependencies of the main container
        #    for the up() phase, if a name for that container is specified in the configuration.

        main_service = self.config.get("up_service") # is the None object, if name not provided

        if not Entire_Project_Built:
            if not main_service:
                print ("ERROR - A comprehensive docker-compose project build was not performed because build stages were given in the config.")
                print ("        But an 'up_service' name was not given, which could result in running out-of-date services.  Exiting.... ")
                exit(2)
            proj.build(service_names = get_ordered_dependencies(proj,main_service),
                       **get_build_options())

        containers = proj.up(service_names = [main_service] if main_service else None)

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

        proj_down_setting = Jenkins.get("project_down_when_client_exits", None)
        print("DWM ::: proj_down_setting = ", proj_down_setting )
        if proj_down_setting:
            proj.down( **Jenkins.get('settings_for_project_down', {}) )

        return status_code


    def _import_yaml_subs_and_environ_vars(self):

        yaml_subs = self.config.get("yaml_substitutions",{})
        with open (join(self.compose_path,".env"),("a" if self.preserve_dotenv else "w")) as dotEnv_file:
            for k,v in yaml_subs.items():
                dotEnv_file.write("{k}={v}\n".format(**locals()))

        environments = self.config.get("container_environments",{})
        for container_name,env_lookup in environments.items():
            with open(join(self.compose_path, container_name+".env"),"a") as containerEnvironment_File:
                for k,v in env_lookup.items():
                    containerEnvironment_File.write("{k}={v}\n".format(**locals()))


    def store_config(self, basic_config, allow_override = True ):
        self.config = copy.deepcopy(basic_config)
        self.config['jenkins_defaults'] = self.__jenkins_defaults
        if allow_override:
            _update_lhs_scalars_with_rhs( self.config,
                                          self.modifier_config )
        return copy.deepcopy(self.config)


if __name__ == '__main__':
    if sys.argv[1:] == ['-test']:
        test()
        p = compose.cli.command.get_project('.')
    else:
        main()
