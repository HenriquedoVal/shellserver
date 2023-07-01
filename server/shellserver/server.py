from __future__ import annotations

from collections import deque
import gc
from io import StringIO
import os
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Any

from win_basic_tools import Ls

from .__init__ import SEP, CONFIG_PATH, USER_HOME
from . import utils
from .style import style
from .gitstatus import interface

try:
    import tomllib
    TomlDecodeError = tomllib.TOMLDecodeError
except ImportError:
    import tomlkit as tomllib
    TomlDecodeError = tomllib.exceptions.TOMLKitError


class Config:
    timeit: bool = False
    disable_git: bool = False
    dark_theme: str = 'Tango Dark'
    light_theme: str = 'Solarized Light'
    trackdir: bool = True
    permanent: bool = False

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

        buf_size = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
        self.dispatcher = utils.Dispatcher(buf_size)

        self.cache = utils.DirCache()
        self.functionalities = {
            '1': self.scan,
            '2': self.shell_manager,
            '3': self.zsearch,
            '4': self.fzfsearch,
            '5': self.list_directory,
            '6': self.theme_manager,
            '7': self.history_search,
            '8': self.get_buffer,
            '9': self.add_to_cache
        }

        self.re_version_pattern = re.compile(r'\d*\.\d*\.\d*')

        self.brackets = deque()
        self.after_brackets = deque()

        self.exes_with_version = {}
        self.exes_without_version = []
        self.exes_to_search = [
            'node', 'g++', 'gcc', 'lua', 'pwsh', 'java', 'rustc', 'dotnet'
        ]

        # can't get all executables versions through the api
        self.exes_to_search_with_winapi = ('pwsh', 'node', 'java')

        self.map_suffix = {
            'node': '.js',
            'g++': '.cpp',
            'gcc': '.c',
            'lua': '.lua',
            'pwsh': ('.ps1', '.psd1', '.psm1'),
            'java': '.java',
            'rustc': '.rs',
            'dotnet': '.cs'
        }
        self.map_lang_name = {
            'node': 'Node',
            'g++': 'Cpp',
            'gcc': 'C',
            'lua': 'Lua',
            'pwsh': 'Pwsh',
            'java': 'Java',
            'rustc': 'Rust',
            'dotnet': 'Csharp'
        }

        # only those that changes defaults
        self.argv_options = {
            'timeit',
            'no-trackdir',
            'no-fallback',
            'no-watchdog',
            'disable-git',
            'use-git',
            'use-pygit2',
            'test-status',
            'linear',
            'no-read-async',
            'multiproc',
            'permanent',
            'let-crash'
        }

        self.server_only = {
            'timeit', 'disable_git', 'enable_git', 'trackdir', 'permanent'
        }

    def shell_manager(self, entry: str, addr: tuple[Any]) -> int | None:
        if entry.startswith('Init'):
            shell = entry.removeprefix('Init')
            self.clients += 1
            self.dispatcher.register(addr, shell)

        elif entry == 'Get':
            self.dispatcher.send_through(
                self.sock, self.cache.completions, addr
            )

        elif entry.startswith('Set'):
            opt = entry.removeprefix('Set')
            self.handle_opt(opt)

        elif entry == 'Exit':
            self.clients -= 1
            if not Config.permanent and self.clients <= 0:
                self.cache.finish()
                return 1

        elif entry == 'Kill':
            self.cache.finish()
            return 1

    def zsearch(self, entry: str, addr: tuple[Any]) -> None:
        # ./path/ -> path
        # .path -> .path
        entry = entry.strip(SEP).removeprefix('.' + SEP).lower()
        result = self.cache.get(entry)
        self.dispatcher.send_through(self.sock, result, addr, prepare=False)

    def fzfsearch(self, entry: str, addr: tuple[Any]) -> None:
        if entry == 'Get':
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
        width, height, opt, *queries = entry.split(';')
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
        # Don't add drive letters as it makes no sense in pwsh.
        dirname = os.path.dirname(cwd)
        if cwd != USER_HOME and Config.trackdir and dirname != cwd:
            changed = self.cache.add(cwd)

            if changed:
                self.dispatcher.set_update()

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

        self.dispatcher.send_through(self.sock, prompt, addr, send_update=True)

    def get_buffer(self, entry: str, addr: tuple[Any]) -> None:
        if isinstance(Config.output, StringIO):
            data = Config.output.getvalue()
            self.dispatcher.send_through(self.sock, data, addr)

            if 'k' not in entry:
                Config.output.seek(0)
                Config.output.truncate(0)

    def add_to_cache(self, path: str, addr: tuple[Any]) -> None:
        changed = self.cache.add(path)
        if changed:
            self.dispatcher.set_update()

    def mainloop(self) -> None:
        while 1:
            entry, addr = self.sock.recvfrom(4096)
            init = time.perf_counter()
            entry = entry.decode()
            prot = entry[0]

            sig_kill = self.functionalities[prot](entry[1:], addr)

            if Config.timeit:
                took = round(time.perf_counter() - init, 5)
                msg = f'Took: {took}s'
                if Config.output:
                    Config.output.write(msg + '\n')
                else:
                    print(msg)

            self.cleanup()

            if sig_kill:
                break

    def get_version_winapi(self, exe: str) -> None:
        version = utils.get_file_version(exe + '.exe')
        if version:
            self.exes_with_version.update({exe: version})
            self.exes_to_search.remove(exe)

    def get_version(self, exe: str) -> None:
        try:
            out, err = subprocess.Popen(
                [exe, '--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            ).communicate()
        except FileNotFoundError:
            return

        if err:
            return

        out = out.splitlines()[0].decode()
        match = self.re_version_pattern.search(out)
        if match:
            self.exes_with_version.update({exe: match.group()})
            self.exes_to_search.remove(exe)

    def handle_opt(self, opt, update: bool = True) -> None:
        # every opt with 'no-' will set False
        val = not opt.startswith('no-')
        opt = opt.removeprefix('no-').replace('-', '_')

        other = ''
        if opt == 'enable_git':
            opt, val = 'disable_git', False
        elif opt == 'use_gitstatus':
            opt, val = 'use_git', False
            other = 'use_pygit2'
        elif opt == 'use_pygit2':
            other = 'use_git'
        elif opt == 'use_git':
            other = 'use_pygit2'

        setattr(Config, opt, val)
        if other:
            setattr(Config, other, False)

        if update and opt not in self.server_only:
            interface.update_conf(opt, val)
            if other:
                interface.update_conf(other, False)

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
        except (FileNotFoundError, TomlDecodeError):
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
            self.handle_opt(opt, update=False)

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

    def init_script(self) -> None:

        gc.disable()

        py_version = sys.version
        py_version = py_version[:py_version.index(' ')]
        self.py_notation = 'Python' + ';' + py_version

        for exe in self.exes_to_search_with_winapi:
            self.get_version_winapi(exe)

        for exe in self.exes_to_search[:]:  # will modify itself
            threading.Thread(target=self.get_version, args=(exe,)).start()

        self.parse_config_file()
        self.parse_argv()

        interface.set_config(Config)
        interface.init()

    def cleanup(self):
        self.brackets.clear()
        self.after_brackets.clear()
        interface.cleanup()
        gc.collect()
