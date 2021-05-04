import re
import time
import docker
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

def compile_EOL_regex(delimiter): return re.compile( b'('       # parentheses mean that we retain the delimiters
                                                    + delimiter
                                                    + b')' )

# --------------------------------

_build_options = {}

def set_build_options(from_dict):
    _build_options.update( from_dict )

def get_build_options( ):
    return dict( _build_options )

# -------------------------------- Multithreaded output spooling docker compose container output to Jenkins console

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


def run_build_containers( project, service_names_in_order ):
    service_lookup = { s.name:s for s in project.services }
    # iterate through the named services, running the build process and CMD phase for each
    # Output should appear on the console for all parts built or commands run.
    for name in service_names_in_order:
        project.build(service_names = [name], **get_build_options())
        s = service_lookup[name]
        c = s.create_container()
        dclient = docker.client.from_env()
        for network_name in s.networks:
            try:
                dclient.networks.get(network_name)
            except docker.errors.NotFound:
                dclient.networks.create(network_name)
        if not getattr(c,'log_stream',None):
            c.attach_log_stream()
        c.start()
        for i in c.log_stream:
            print ('>> '+i.decode('utf8'))
        w = c.wait()
        print(s.name,'returned',w)


# -------------------------------- Generate dependencies list for the main Container for building

def get_ordered_dependencies(prj,svc_name,ser=None,pdict=None,order=(),seen=()):
    '''Given:
       - prj, the compose project returned by get_project().
       - svc_name, the name of the service for the main CI test container (whose exit status determines success).

    Calculate list of names of all svc_name's dependents that must be built (inclusive of svc_name, which will be last).
    '''
    if pdict is None:
        pdict = {svc.name:svc for svc in prj.services}
    if order == ():
        tmp_order = dict(order)  # initialize ordering dictionary at root of recursion
    else:
        tmp_order = order
    seen = dict(seen) if seen == () else seen
    ser = [0] if ser is None else ser
    dep_names = pdict[svc_name].get_dependency_names()
    tmp_order[svc_name] = ser[0]
    ser[0] += 1
    seen[svc_name]=1
    for name in dep_names:
        if not seen.get(name):
            get_ordered_dependencies(prj,name,ser,pdict,tmp_order)
    if order == ():
        return [k for k,v in sorted(tmp_order.items(), key=lambda _:_[1],reverse=True)]

