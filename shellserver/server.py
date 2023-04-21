from __future__ import annotations

from collections import deque
import gc
from io import StringIO
import os
import socket
import subprocess
import sys
import threading
import time
from typing import Any

from win_basic_tools import Ls

from .__init__ import APP_HOME, SEP, CONFIG_PATH, USER_HOME
from . import utils
from .style import style
from .gitstatus import interface

try:
    import tomllib
except ImportError:
    import tomlkit as tomllib


class Config:
    timeit: bool = False
    disable_git: bool = False
    dark_theme: str = 'Tango Dark'
    light_theme: str = 'Solarized Light'

    # for gitstatus
    use_git: bool
    use_pygit2: bool
    git_timeout: int
    let_crash: bool
    test_status: bool
    linear: bool
    watchdog: bool
    multiproc: bool
    workers: int
    read_async: bool
    fallback: bool
    output: str | None


class Server:

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.clients = 0
        self.dispatcher = utils.Dispatcher()
        self.cache = utils.DirCache()
        self.exes_with_version = {}
        self.brackets = deque()
        self.after_brackets = deque()
        self.exes_to_search = ['node', 'g++', 'gcc', 'lua', 'pwsh']

        self.map_suffix = {
            'node': '.js',
            'g++': '.cpp',
            'gcc': '.c',
            'lua': '.lua',
            'pwsh': ('.ps1', '.psd1', '.psm1')
        }
        self.map_lang_name = {
            'node': 'Node',
            'g++': 'Cpp',
            'gcc': 'C',
            'lua': 'Lua',
            'pwsh': 'Pwsh'
        }
        self.argv_options = {
            'timeit',
            'no-fallback',
            'no-watchdog',
            'disable-git',
            'use-git',
            'use-pygit2',
            'test-status',
            'linear',
            'multiproc',
            'read-async',
            'let-crash'
        }
        self.server_only = {'timeit', 'disable_git', 'enable_git'}

    def shell_manager(self, entry: str, addr: tuple[Any]) -> None:
        if entry.startswith('Init'):
            shell = entry.removeprefix('Init')
            self.dispatcher.register(addr, shell)
            self.clients += 1
            completions = ';'.join(item[2] for item in self.cache.dirs)
            self.dispatcher.send_through(self.sock, completions, addr)

        elif entry.startswith('Set'):
            opt = entry.removeprefix('Set')

            # every opt with 'no-' will set False
            val = not opt.startswith('no-')
            opt = opt.removeprefix('no-').replace('-', '_')

            if opt in self.server_only:
                if opt == 'enable_git':
                    Config.disable_git = False
                else:
                    setattr(Config, opt, val)
                return

            elif opt == 'use_gitstatus':
                opt, val = 'use_git', False
                interface.update_conf('use_pygit2', False)

            interface.update_conf(opt, val)

        elif entry == 'Exit':
            self.clients -= 1
            if self.clients <= 0:
                self.cache.finish()
                raise SystemExit

        elif entry == 'Kill':
            self.cache.finish()
            raise SystemExit

    def zsearch(self, entry: str, addr: tuple[Any]) -> None:
        # ./path/ -> path
        # .path -> .path
        entry = entry.strip(SEP).removeprefix('.' + SEP).lower()
        result = self.cache.get(entry)
        self.dispatcher.send_through(self.sock, result, addr, prepare=False)

    def fzfsearch(self, entry: str, addr: tuple[Any]) -> None:
        if not entry:  # if its the first
            result = '\n'.join([i[1] for i in self.cache.dirs])
            self.dispatcher.send_through(self.sock, result, addr)
        else:
            self.cache.update_by_full_path(entry)
            self.cache.sort()

    def list_directory(self, entry: str, addr: tuple[Any]) -> None:
        opt, path = entry.split(';')
        path = path.removeprefix('Microsoft.PowerShell.Core\\FileSystem::')

        # Ls class can handle symlink
        ls = Ls(opt, path, to_cache=True)
        ls.echo()
        res = ls.out.getvalue()

        self.dispatcher.send_through(self.sock, res, addr)

    def theme_manager(self, entry: str, addr: tuple[Any]) -> None:
        try:
            if entry in ('all', ''):
                utils.call_all_theme_funcs()
            elif entry == 'terminal':
                utils.windows_terminal_change(Config)
            elif entry == 'blue':
                utils.toggle_blue_light_reduction()
            elif entry == 'system':
                utils.system_theme_change()
        except Exception:
            pass

    def history_search(self, entry: str, addr: tuple[Any]) -> None:
        queries, width, height, opt = entry.split(';')
        width, height = int(width), int(height)

        res = utils.history_search(queries, width, height, opt)
        self.dispatcher.send_through(self.sock, res, addr)

    def _get_paths(self, cwd: str) -> tuple[str, str, str]:
        # Microsoft.PowerShell.Core\Registry::
        cwd = cwd.removeprefix('Microsoft.PowerShell.Core\\')
        # os.realpath can handle \\wsl$\Distro
        cwd = cwd.removeprefix('FileSystem::')

        link = os.path.realpath(cwd)
        if not os.path.exists(link):
            link = cwd

        target_dir = cwd if cwd == link else link

        return cwd, link, target_dir

    def scan(self, entry: str, addr: tuple[Any]) -> None:
        no_error = int(entry[0])
        cwd, width, duration = entry[1:].split(';')

        width = int(width)
        duration = round(float(duration.replace(',', '.')), 1)

        # must add before cleanup because Set-Location needs full 'path'
        if cwd != USER_HOME:
            self.cache.add(cwd)

        cwd, link, target_dir = self._get_paths(cwd)

        if not Config.disable_git:
            branch, status = interface.gitstatus(target_dir)
            if branch is not None:
                self.brackets.append(f'Branch;{branch}')
            if status is not None:
                self.brackets.append(f'Status;{status}')

        try:
            directory = os.scandir(target_dir)
        except PermissionError:
            self.brackets.append('Error;Permission')
            directory = tuple()
        except OSError:
            directory = tuple()

        for file in directory:
            if (
                    self.py_notation not in self.brackets
                    and file.name.endswith(
                        ('.py', '.pyc', '.pyw', '.pyd', '.pyi')
                    )
            ):
                self.brackets.append(self.py_notation)

            for exe in self.exes_with_version:
                notation = (
                    f'{self.map_lang_name[exe]};{self.exes_with_version[exe]}'
                )
                condition1 = notation not in self.brackets
                if condition1 and file.name.endswith(self.map_suffix[exe]):
                    self.brackets.append(notation)

            for exe in self.exes_to_search:  # those who don't have version
                notation = self.map_lang_name[exe]
                if (notation not in self.after_brackets
                   and file.name.endswith(self.map_suffix[exe])):
                    self.after_brackets.append(notation)

        prompt = style(
            cwd, link, self.brackets,
            self.after_brackets, no_error, width, duration
        )

        self.dispatcher.send_through(self.sock, prompt, addr)

    def get_version(self, exe: str) -> None:
        try:
            out, err = subprocess.Popen(
                f'{exe} --version',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).communicate()
        except FileNotFoundError:
            return

        if err:
            return

        if exe in ('g++', 'gcc'):
            out = out.splitlines()[0]
            out = out[out.rindex(b')') + 2:]
            self.exes_with_version.update({exe: out.strip().decode()})
            self.exes_to_search.remove(exe)
        elif exe == 'node':
            self.exes_with_version.update({exe: out.strip().decode()[1:]})
            self.exes_to_search.remove(exe)
        elif exe == 'pwsh':
            self.exes_with_version.update(
                {exe: out.split()[-1].strip().decode()}
            )
            self.exes_to_search.remove(exe)

    def handle_output(self, got: str) -> None:
        if got is None:
            Config.output = None
        elif got == 'stdout':
            Config.output = sys.stdout
        elif got == 'buffer':
            Config.output = StringIO()
        else:
            try:
                s = open(got, 'a')
                Config.output = s
            except Exception:
                Config.output = None

    def parse_config_file(self) -> None:
        try:
            s = open(CONFIG_PATH, 'rb')
            toml = tomllib.load(s)
            s.close()
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            toml = {}

        for config, type_ in Config.__annotations__.items():
            got = toml.get(config)

            if config == 'output':
                self.handle_output(got)
            elif got is not None and isinstance(got, eval(type_)):
                setattr(Config, config, got)

    def parse_argv(self) -> None:
        parsed_argv = self.argv_options.intersection(
            {i.lstrip('--') for i in sys.argv}
        )

        # sets only known opts
        for opt in parsed_argv:
            if opt == 'no-fallback':
                Config.fallback = False
            elif opt == 'no-watchdog':
                Config.watchdog = False
            else:
                opt = opt.replace('-', '_')
                setattr(Config, opt, True)

        for opt in [arg for arg in sys.argv if '=' in arg]:
            opt = opt.lstrip('--')
            cmd, value = opt.split('=')
            if not value:
                continue

            if cmd == 'output':
                self.handle_output(value)
                continue

            try:
                int_value = int(value)
            except Exception:
                continue

            if cmd == 'git-timeout':
                Config.git_timeout = int_value
            elif cmd == 'workers':
                Config.workers = int_value

    def mainloop(self) -> None:
        while 1:
            entry, addr = self.sock.recvfrom(4096)
            init = time.perf_counter()
            entry = entry.decode()
            prot = entry[0]

            self.functionalities[prot](entry[1:], addr)

            if Config.timeit:
                took = round(time.perf_counter() - init, 5)
                print(f'Took: {took}s')

            self.cleanup()

    def init_script(self) -> None:

        gc.disable()
        os.makedirs(APP_HOME, exist_ok=True)

        entries = map(str, range(1, 8))
        defined_functions = (
            self.scan,
            self.shell_manager,
            self.zsearch,
            self.fzfsearch,
            self.list_directory,
            self.theme_manager,
            self.history_search
        )
        self.functionalities = dict(zip(entries, defined_functions))

        py_version = sys.version
        py_version = py_version[:py_version.index(' ')]
        self.py_notation = 'Python' + ';' + py_version

        for exe in self.exes_to_search:
            threading.Thread(target=self.get_version, args=(exe,)).start()

        self.parse_config_file()
        self.parse_argv()

        interface.set_config(Config)
        interface.init()

    def cleanup(self):
        self.brackets.clear()
        self.after_brackets.clear()
        gc.collect()
