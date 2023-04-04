import socket

from .__init__ import APP_HOME, PORT, SEP, CONFIG_PATH, USER_HOME

# Quit program as soon as possible
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('localhost', PORT))
except OSError:
    raise SystemExit


import gc
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from win_basic_tools import Ls

from . import histdb, theme
from .gitstatus.main import gitstatus
from .classes import DirCache, Dispatcher
from .style import style

try:
    import tomllib
except ImportError:
    import tomlkit as tomllib


gc.disable()


@dataclass
class Config:
    git_timeout: int = 2500
    dark_theme: str = 'Tango Dark'
    light_theme: str = 'Solarized Light'


def shell_manager(entry: str, addr) -> None:
    global clients

    if entry.startswith('Init'):
        shell = entry.removeprefix('Init')
        dispatcher.register(addr, shell)
        clients += 1
        completions = ';'.join(item[2] for item in cache.dirs)
        dispatcher.send_through(sock, completions, addr)

    elif entry.startswith('Set'):
        option = '--' + entry.removeprefix('Set')
        if option == '--enable-git':
            try:
                sys.argv.remove('--disable-git')
            except ValueError:
                pass
            return
        if option == '--use-gitstatus':
            try:
                sys.argv.remove('--use-git')
            except ValueError:
                pass
            return
        if option == '--verbose':
            sys.stdout = sys.__stdout__
        sys.argv.append(option)

    elif entry == 'Exit':
        clients -= 1
        if clients <= 0:
            cache.finish()
            raise SystemExit

    elif entry == 'Kill':
        cache.finish()
        raise SystemExit


def zsearch(entry: str, addr: int) -> None:
    # ./path/ -> path
    # .path -> .path
    entry = entry.strip(SEP).removeprefix('.' + SEP).lower()
    result = cache.get(entry)
    dispatcher.send_through(sock, result, addr, prepare=False)


def fzfsearch(entry: str, addr: int) -> None:  # will receive two calls by 'pz'
    if not entry:  # if its the first
        result = '\n'.join([i[1] for i in cache.dirs])
        dispatcher.send_through(sock, result, addr)
    else:
        cache.update_by_full_path(entry)
        cache.sort()


def list_directory(entry: str, addr: int) -> None:
    opt, path = entry.split(';')
    path = path.removeprefix('Microsoft.PowerShell.Core\\FileSystem::')

    # Ls class can handle symlink
    ls = Ls(opt, path, to_cache=True)
    ls.echo()

    dispatcher.send_through(sock, ls.out.data, addr)


def theme_manager(entry: str, addr) -> None:
    try:
        if entry in ('all', ''):
            theme.all()
        elif entry == 'terminal':
            theme.windows_terminal_change(config)
        elif entry == 'blue':
            theme.night_light_change()
        elif entry == 'system':
            theme.system_change()
    except Exception:
        pass


def history_search(entry: str, addr) -> None:
    queries, width, height = entry.split(';')
    width, height = int(width), int(height)

    res = histdb.main(queries, width, height)
    dispatcher.send_through(sock, res, addr)


def _get_paths(cwd):
    # Microsoft.PowerShell.Core\Registry::
    cwd = cwd.removeprefix('Microsoft.PowerShell.Core\\')
    # os.realpath can handle \\wsl$\Distro
    cwd = cwd.removeprefix('FileSystem::')

    # Python 3.10+
    # try:
    #     link = os.path.realpath(cwd, strict=True)
    # except OSError:
    #     #  Env:, Function:, Alias:, ...
    #     link = cwd

    # Workaround. Can lead to errors
    link = os.path.realpath(cwd)
    if not os.path.exists(link):
        link = cwd

    target_dir = cwd if cwd == link else link

    return cwd, link, target_dir


def scan(entry, addr):
    no_error = int(entry[0])
    cwd, width, duration = entry[1:].split(';')

    width = int(width)
    duration = round(float(duration.replace(',', '.')), 1)

    # must add before cleanup because Set-Location needs full 'path'
    if cwd != USER_HOME:
        cache.add(cwd)

    cwd, link, target_dir = _get_paths(cwd)

    brackets = []
    after_brackets = []

    branch, status = gitstatus(target_dir, config)
    if branch is not None:
        brackets.append(f'Branch;{branch}')
        if status:
            brackets.append(f'Status;{status}')

    git_flag = bool(branch)

    try:
        directory = os.scandir(target_dir)
    except PermissionError:
        brackets.append('Error;Permission')
        directory = tuple()
    except OSError:
        directory = tuple()

    for file in directory:
        if (py_not not in brackets
           and file.name.endswith(('.py', '.pyc', '.pyw', '.pyd', '.pyi'))):
            brackets.append(py_not)

        for exe in exes_with_version:
            notation = f'{map_lang_name[exe]};{exes_with_version[exe]}'
            condition1 = notation not in brackets
            if condition1 and file.name.endswith(map_suffix[exe]):
                brackets.append(notation)

        for exe in exes_to_search:  # those who don't have version
            notation = map_lang_name[exe]
            if (notation not in after_brackets
               and file.name.endswith(map_suffix[exe])):
                after_brackets.append(notation)

    prompt = style(
        cwd, link, git_flag, brackets,
        after_brackets, no_error, width, duration
    )

    dispatcher.send_through(sock, prompt, addr)


def mainloop():
    while 1:
        entry, addr = sock.recvfrom(4096)
        init = time.perf_counter()
        entry = entry.decode()
        prot = entry[0]

        functionalities[prot](entry[1:], addr)

        if '--verbose' in sys.argv:
            took = round(time.perf_counter() - init, 5)
            print(f'Took: {took}s')

        gc.collect()


#
# Updating the executables that will be searched starts here
#


def get_version(exe) -> None:
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
        exes_with_version.update({exe: out.strip().decode()})
        exes_to_search.remove(exe)
    elif exe == 'node':
        exes_with_version.update({exe: out.strip().decode()[1:]})
        exes_to_search.remove(exe)
    elif exe == 'pwsh':
        exes_with_version.update({exe: out.split()[-1].strip().decode()})
        exes_to_search.remove(exe)


exes_to_search = ['node', 'g++', 'gcc', 'lua', 'pwsh']

map_suffix = {
    'node': '.js',
    'g++': '.cpp',
    'gcc': '.c',
    'lua': '.lua',
    'pwsh': ('.ps1', '.psd1', '.psm1')
}
map_lang_name = {
    'node': 'Node',
    'g++': 'Cpp',
    'gcc': 'C',
    'lua': 'Lua',
    'pwsh': 'Pwsh'
}

#
# Stop here
#

os.makedirs(APP_HOME, exist_ok=True)

entries = map(str, range(1, 8))
defined_functions = (
    scan,
    shell_manager,
    zsearch,
    fzfsearch,
    list_directory,
    theme_manager,
    history_search
)
functionalities = dict(zip(entries, defined_functions))

clients = 0
cache = DirCache()
dispatcher = Dispatcher()

py_version = sys.version
py_version = py_version[:py_version.index(' ')]
py_not = 'Python' + ';' + py_version  # notation

exes_with_version = {}

for exe in exes_to_search:
    threading.Thread(target=get_version, args=(exe,)).start()

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'rb') as file:
        toml = tomllib.load(file)
else:
    toml = {}

try:
    config = Config(
        git_timeout=int(toml.get('git_timeout', 2500)),
        dark_theme=str(toml.get('dark_theme', 'Tango Dark')),
        light_theme=str(toml.get('light_theme', 'Solarized Light'))
    )
except ValueError:
    config = Config()
