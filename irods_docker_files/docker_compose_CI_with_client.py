#!/usr/bin/env python3

from __future__ import print_function
import argparse
import subprocess
import os
import re
import sys
import json
from pprint import pformat
from os.path import join
import compose.cli.command

def print_(*x): return None # print(*x,file=sys.stderr)

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
    print_ ("before CI object ctor - modifiers_for_config = ",modifiers_for_config)

    if Args.dry_run:
      print(json.dumps(modifiers_for_config,indent=4))
      exit(126)


    subprocess.check_output(['git', 'clone', '--recurse-submodules', '-q',
                             Args.remote_repository, Args.local_repository ])

    subprocess.check_output(['git', 'checkout', Args.commitish], cwd=Args.local_repository)

#   -- sample modifier config --
#   {
#     "yaml_substitutions": { "db": "postgres",
#                             "db_port": "5432" },
#     "container_environments":
#         { "icat-db" : { },
#           "irods-provider" : { } ,
#           "client-runner" : { "PY_VERSION": "3", "IRODS_HOST": "irods-provider" }
#         },
#     "host_output_directory":"/tmp"
#   }

    # Find the docker compose project in the cloned client repo,
    #  and import the module that runs the test
    #

    os.chdir( Args.local_repository )
    print( "cd'd into local repo = ", os.getcwd( ), file=sys.stderr)

#####project = compose.cli.command.get_project(".")

    import importlib
    sys.path.insert(0, ".")
    test_hook = importlib.import_module('test_hook')
    
    # The following runs the test_hook module imported from client repo. That module's
    # run() function calls back to the injected object (of class 'CI_client_interface'
    # - defined below):
    #
    print_ ("before CI object ctor - modifiers_for_config = ",modifiers_for_config)
    exit(test_hook.run(
        CI_client_interface (modifiers_for_config, ".", None)
    ))


class CI_client_interface (object):

    def __init__(self, modifier_config, compose_dir, compose_project):

        print_ ("CI object ctor - modifier_config",modifier_config)
        self.modifier_config = modifier_config
        self.config = {}
        self.compose_prj = compose_project
        self.compose_path = os.path.abspath(compose_dir)

    def run_and_wait_on_client_exit( self,
                                     name_pattern = '[-_]client-runner[-_]',
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
            proj = compose.cli.command.get_project(".")
        proj.build()		# build and run from docker-compose.yml
        containers = self.compose_prj = proj.up()

        # -- Match client container by name, wait and collect status
        #
        rgx = re.compile(name_pattern, rgx_flags)
        status_containers = [ c for c in containers if rgx.search(c.name) ]

        if len(status_containers) != 1:
            raise RuntimeError("Exactly one container can be waited on for CI status, but the"
                               "names of {} containers were matched".format(len(status_containers)))
        status_code = status_containers[0].wait()

        # -- Stop the other containers
        #
        for c in set(containers) - set([status_containers[0]]):
            c.stop()

        # -- Return client status
        #
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
        x = 1


    def store_config(self, basic_config, allow_override = True ):
        print_ ("store_config RAN ***" )
        self.config = basic_config.copy()
        def update_lhs_scalars_with_rhs (lhs, rhs, keys=()):
            print_("in update lhs withi rhs-----lhs={},rhs={},keys={}".format(lhs,rhs,keys))
            key_hierarchy = lambda newkey: list(keys)+[newkey]
            for k,v in rhs.items():
                print_ ("RHS key = ",k,"value = ",v);
                v_lhs = lhs.get(k,None)
                #if v_lhs is None or type(v) is type(v_lhs):
                print_( 'check type v from rhs =',v,' vs. v_lhs = ',v_lhs)
                if type(v) is type(v_lhs):
                    print_( 'types matched for ',k)
                    if type(v) is dict:
                        print_( 'value was dict for ',k)
                        update_lhs_scalars_with_rhs( lhs[k] , rhs[k], key_hierarchy(k) )
                    else:
                        print_( 'value was NOT dict for ',k)
                        lhs [k] = rhs [k]
                else:
                    print_( 'types did not match for ',k)
                    print_ ('-- Warning -- Mismatch of value type in basic and modifier configs at '
                             '{!r}'.format(key_hierarchy(k)), file = sys.stderr)

        if allow_override:
            print_("-NEAR END -- overriding")
            update_lhs_scalars_with_rhs( self.config, self.modifier_config )

        print_("----AT END -------self.config  = ",self.config)

        return self.config.copy()

if __name__ == '__main__':
    main()
