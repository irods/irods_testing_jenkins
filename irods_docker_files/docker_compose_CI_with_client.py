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
from pprint import pformat
from os.path import join
import compose.cli.command

class testgen:
    def __init__(self,file_,tm=0.15):
        self.file = (file_ if getattr(file_,'read',None) else open(file_,"rb"))
        self.tm = tm
    def __iter__(self):
        with self.file as f:
          x = '.'
          while x:
            x = f.read(2)
            time.sleep(self.tm)
            if x: yield x

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


def compile_EOL_regex(delimiter): return re.compile( b'('       # parentheses mean that we retain the delimiters
                                                    + delimiter
                                                    + b')' )

class readgen:

    MAX_LINE_ELEMENTS = 256
    EOL_splitters = { delim:compile_EOL_regex(delim) for delim in [b'\n',b'\r\n'] }
    EOL_splitters[b''] = re.compile(b'(.+)',re.DOTALL)
    class IllegalDelimiter(RuntimeError): pass

    class dummyLock:
        def __enter__(self): pass
        def __exit__(self,*x): pass

    def __init__(self, files_ , file_locks_ = ()):
        self.buf = []
        self.files = files_
        self.fileLocks = dict(file_locks_)
        self.ident = ''

    # Get a piece of the container log_stream's output to be printed to console.
    # (Usually will consist of zero or more lines)

    def get_buffered_content(self, new_chars=b'', delim = b'\n'): # b'\n' => output only whole lines
                                                                  # b''   => output all of buffer (flush)
        log_lines = b''
        if not isinstance(new_chars,bytes):
            new_chars = str(new_chars).encode('utf-8')
        self.buf.append(new_chars)
        if delim in new_chars or len(self.buf) > self.MAX_LINE_ELEMENTS:
            regexSplitter = self.EOL_splitters.get(delim)
            if regexSplitter is None:
                if isinstance(delim,bytes): regexSplitter = self.compile_EOL_regex(delim)
                else:                       raise self.IllegalDelimiter('cannot make delimiter of: {!r}'.format(delim))
            buf = regexSplitter.split(b''.join(self.buf)) + [b'']
            cut_offs = 0; last = 1                            # Calculate the negative end-offset of the
            if isinstance(delim,bytes) and len(delim) >= 1:   # last chunk containing a 'delim' character.
                for chunk in reversed( buf[-3:-1] ):          # This will always be 1 for a flush operation.
                    last += 1
                    if chunk.startswith(delim):
                        cut_offs=1
                        break
            log_lines += b''.join(buf[:-last])
            self.buf = list(filter(None,buf[-last+cut_offs:]))
        else:
            pass
#######
# dwm #
      # if 'runner' in  self.ident:
      #     log_lines = '*** dwm *** LEN of els in line buffer = {!r}'.format([len(x) for x in self.buf]).encode('utf-8')
      # # dwm DEBUG -- # print('\t self.buf=', self.buf,file=sys.stderr)
#######
        return log_lines

    # Thread entry point.

    def __call__(self, log_generator, ident_ = None) :
        def stream_out(Lines):
            if not Lines: return
            for f in self.files:
                with self.fileLocks.get(f,self.dummyLock()):
                    for line in Lines:
                        f.write("(" + self.ident + ") -- | " + line.decode("utf-8") + "\n")
        if ident_ is None: ident_ = '<{}>'.format(id(self))
        self.ident = ident_
        for chunk in log_generator:
            stream_out (self.get_buffered_content(chunk, delim = b'\n').splitlines())
        stream_out (self.get_buffered_content(b'', delim = b'').splitlines())


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
            proj = compose.cli.command.get_project( self.compose_path )

        proj.build()            # build and run from docker-compose.yml
        containers = self.compose_prj = proj.up()

        # -- Match client container by name for status reporting
        #
        rgx = re.compile(name_pattern, rgx_flags)
        status_containers = [ c for c in containers if rgx.search(c.name) ]

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
    else:
        main()
