class DockerCommandsBuilder(object):
    def __init__(self):
        self.machine_name = None
        self.build_mount = None
        self.upgrade_mount = None
        self.plugin_mount = None
        self.results_mount = None
        self.cgroup_mount = '/sys/fs/cgroup:/sys/fs/cgroup:ro'
        self.key_mount = None
        self.run_mount = None
        self.externals_mount = None
        self.mysql_mount = None
        self.image_name = None
        self.python_script = None
        self.database_type = None
        self.test_name = None
        self.test_type = None
        self.plugin_repo = None
        self.plugin_commitish = None
        self.passthru_args = None
        self.is_unit_test = False
        self.is_provider = False
        self.use_ssl = False
        self.database_machine = None
        self.docker_socket = '/var/run/docker.sock:/var/run/docker.sock'
        self.machine_list = None
        self.hostname = 'icat.example.org'
        self.zone_name = 'tempZone'
        self.remote_zone = 'icat.tempZone.example.org'

    def set_machine_name(self, machine_name):
        self.machine_name = machine_name

    def set_build_mount(self, build_mount):
        self.build_mount = build_mount

    def set_upgrade_mount(self, upgrade_mount):
        self.upgrade_mount = upgrade_mount

    def set_plugin_mount(self, plugin_mount):
        self.plugin_mount = plugin_mount

    def set_results_mount(self, results_mount):
        self.results_mount = results_mount

    def set_cgroup_mount(self, cgroup_mount):
        self.cgroup_mount = cgroup_mount

    def set_key_mount(self, key_mount):
        self.key_mount = key_mount

    def set_externals_mount(self, externals_mount):
        self.externals_mount = externals_mount

    def set_image_name(self, image_name):
        self.image_name = image_name

    def set_run_mount(self, run_mount):
        self.run_mount = run_mount

    def set_mysql_mount(self, mysql_mount):
        self.mysql_mount = mysql_mount

    def set_python_script(self, python_script):
        self.python_script = python_script

    def set_database_type(self, database_type):
        self.database_type = database_type

    def set_test_name(self, test_name):
        self.test_name = test_name

    def set_test_type(self, test_type):
        self.test_type = test_type

    def set_plugin_repo(self, plugin_repo):
        self.plugin_repo = plugin_repo

    def set_plugin_commitish(self, plugin_commitish):
        self.plugin_commitish = plugin_commitish

    def set_passthru_args(self, passthru_args):
        self.passthru_args = passthru_args

    def set_is_unit_test(self, is_unit_test):
        self.is_unit_test = is_unit_test

    def set_is_provider(self, is_provider):
        self.is_provider = is_provider

    def set_use_ssl(self, use_ssl):
        self.use_ssl = use_ssl

    def set_database_machine(self, database_machine):
        self.database_machine = database_machine

    def set_docker_socket(self, docker_socket):
        self.docker_socket = docker_socket

    def set_machine_list(self, machine_list):
        self.machine_list = machine_list

    def set_hostname(self, hostname):
        self.hostname = hostname

    def set_zone_name(self, zone_name):
        self.zone_name = zone_name

    def set_remote_zone(self, remote_zone):
        self.remote_zone = remote_zone

    def plugin_constructor(self, machine_name, build_mount, plugin_mount, results_mount, key_mount, mysql_mount, run_mount, externals_mount, image_name, python_script, database_type, plugin_repo, plugin_commitish, passthru_args):
        self.set_machine_name(machine_name)
        self.set_build_mount(build_mount)
        self.set_plugin_mount(plugin_mount)
        self.set_results_mount(results_mount)
        self.set_key_mount(key_mount)
        self.set_mysql_mount(mysql_mount)
        self.set_externals_mount(externals_mount)
        self.set_image_name(image_name)
        self.set_run_mount(run_mount)
        self.set_python_script(python_script)
        self.set_database_type(database_type)
        self.set_plugin_repo(plugin_repo)
        self.set_plugin_commitish(plugin_commitish)
        self.set_passthru_args(passthru_args)

    def core_constructor(self, machine_name, build_mount, upgrade_mount, results_mount, run_mount, externals_mount, mysql_mount, image_name, python_script, database_type, test_name, test_type, is_unit_test, is_provider, database_machine):
        self.set_machine_name(machine_name)
        self.set_build_mount(build_mount)
        self.set_upgrade_mount(upgrade_mount)
        self.set_results_mount(results_mount)
        self.set_externals_mount(externals_mount)
        self.set_mysql_mount(mysql_mount)
        self.set_image_name(image_name)
        self.set_run_mount(run_mount)
        self.set_python_script(python_script)
        self.set_database_type(database_type)
        self.set_test_name(test_name)
        self.set_test_type(test_type)
        self.set_is_unit_test(is_unit_test)
        self.set_is_provider(is_provider)
        self.set_database_machine(database_machine)

    def build_run_cmd(self):
        cmd = ['docker', 'run', '-d', '--rm', 
                '-h', self.hostname,
                '--name', self.machine_name,
                '-v', self.build_mount,
                '-v', self.results_mount,
                '-v', self.cgroup_mount]
        if self.plugin_mount is not None:
            cmd.append('--privileged')
        elif self.plugin_mount is None and not self.database_type == 'oracle':
            cmd.extend(['--cap-add', 'SYS_ADMIN', '--device', '/dev/fuse', '--security-opt', 'apparmor:unconfined'])
        if self.upgrade_mount is not None and not 'None' in self.upgrade_mount:
            cmd.extend(['-v', self.upgrade_mount])
        if self.plugin_mount is not None:
            cmd.extend(['-v',self.plugin_mount])
        if self.run_mount is not None:
            cmd.extend(['-v',self.run_mount])
        if self.externals_mount is not None and not 'None' in self.externals_mount:
            cmd.extend(['-v', self.externals_mount])
        if self.key_mount is not None and 's3' in self.machine_name:
            cmd.extend(['-v', self.key_mount])
        if self.database_type == 'mysql' and self.mysql_mount is not None:
            cmd.extend(['-v', self.mysql_mount])
        if self.database_type == 'oracle' and self.docker_socket is not None:
            cmd.extend(['-v', self.docker_socket])
        if self.test_type is not None:
            if 'topology' in self.test_type or 'federation' in self.test_type:
                cmd.extend(['-v', self.docker_socket])
                cmd.extend(['--expose', '1248', '--expose', '1247', '-P'])
        cmd.append(self.image_name)
        return cmd

    def build_exec_cmd(self):
        cmd = ['docker', 'exec', self.machine_name, 'python', self.python_script,
                '--database_type', self.database_type]
        if self.test_name is not None:
            cmd.extend(['--test_name', self.test_name])
        if self.is_unit_test:
            cmd.append('--unit_test')
        if self.upgrade_mount is not None and not 'None' in self.upgrade_mount:
            cmd.append('--upgrade_test')
        if self.externals_mount is not None and not 'None' in self.externals_mount:
            cmd.append('--install_externals')
        if self.plugin_mount is not None:
            cmd.append('--test_plugin')
        if self.plugin_repo is not None:
            cmd.extend(['--plugin_repo', self.plugin_repo])
        if self.plugin_commitish is not None:
            cmd.extend(['--plugin_commitish', self.plugin_commitish])
        if self.passthru_args is not None:
            cmd.extend(['--passthrough_arguments', str(self.passthru_args)])
        if self.database_machine is not None:
            cmd.extend(['--database_machine', self.database_machine])
        if self.test_type is not None:
            if 'topology' in self.test_type or 'federation' in self.test_type:
                cmd.extend(['--alias_name', self.hostname, '--test_type', self.test_type])
        if self.test_type is not None and 'federation' in self.test_type:
            cmd.extend(['--zone_name', self.zone_name, '--remote_zone', self.remote_zone])
        if self.is_provider and 'topology' in self.test_type:
            cmd.append('--is_provider')
        if self.use_ssl and 'topology' in self.test_type:
            cmd.append('--use_ssl')
        return cmd

    def build_stop_cmd(self):
        cmd = ['docker', 'stop', self.machine_name]
        return cmd
        


