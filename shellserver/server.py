import socket

from .__init__ import APP_HOME, PORT, SEP

# Quit program as soon as possible
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('localhost', PORT))
except OSError:
    raise SystemExit

import os
import subprocess
import sys
import threading
import time

from win_basic_tools.ls import Ls

from . import histdb, theme
from .gitstatus import gitstatus
from .cache import DirCache
from .dispatch import Dispatcher
from .style import style


def shell_manager(entry: str, addr) -> None:
    if entry.startswith('Init'):
        shell = entry.removeprefix('Init')
        dispatcher.register(addr, shell)
        clients.append(1)
        completions = ';'.join(item[2] for item in cache.dirs)
        dispatcher.send_through(sock, completions, addr)

    elif entry == 'Exit':
        try:
            clients.pop()
        except IndexError:
            pass
        if not clients:
            cache.finish()
            raise SystemExit

    elif entry == 'Kill':
        cache.finish()
        raise SystemExit


def zsearch(entry: str, addr: int) -> None:
    entry = entry.strip('.' + SEP).lower()
    result = cache.get(entry)
    dispatcher.send_through(sock, result, addr)


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
    ls.echo(0)

    dispatcher.send_through(sock, ls.out.data, addr)


def theme_manager(entry: str) -> None:
    try:
        if entry in ('all', ''):
            theme.all()
        elif entry == 'terminal':
            theme.windows_terminal_change()
        elif entry == 'blue':
            theme.night_light_change()
        elif entry == 'system':
            theme.system_change()
    except:
        pass


def history_search(entry: str, addr) -> None:
    queries, width, height = entry.split(';')
    width, height = int(width), int(height)

    res = histdb.main(queries, width, height)
    dispatcher.send_through(sock, res, addr)


def scan(entry, addr):
    no_error = int(entry[0])
    curdir, width, duration = entry[1:].split(';')
    width = int(width)
    duration = round(float(duration.replace(',', '.')), 1)

    if curdir != home:
        cache.add(curdir)

    # Wsl
    curdir = curdir.removeprefix('Microsoft.PowerShell.Core\\FileSystem::')

    link = os.path.realpath(curdir)

    brackets = []
    after_brackets = []

    git_flag = False
    branch, status = gitstatus(curdir)
    if branch is not None:
        git_flag = True
        brackets.append(f'Branch;{branch}')
        if status:
            brackets.append(f'Status;{status}')

    target_dir = curdir if curdir == link else link
    try:
        with os.scandir(target_dir) as directory:
            for file in directory:
                if (py_not not in brackets
                   and file.name.endswith(('.py', '.pyc', '.pyw', '.pyd'))):
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
    except PermissionError:
        brackets.append('Error;Permission')
    except OSError:
        pass

    if home in curdir:
        curdir = '~' + curdir.removeprefix(home)
    if home in link:
        link = '~' + link.removeprefix(home)

    prompt = style(
        curdir, link, git_flag, brackets,
        after_brackets, no_error, width, duration
    )

    dispatcher.send_through(sock, prompt, addr)


def mainloop():
    while 1:
        entry, addr = sock.recvfrom(4096)
        init = time.perf_counter()
        entry = entry.decode()

        if entry.startswith('1'):
            scan(entry[1:], addr)

        elif entry.startswith('2'):
            shell_manager(entry[1:], addr)

        elif entry.startswith('3'):
            zsearch(entry[1:], addr)

        elif entry.startswith('4'):
            fzfsearch(entry[1:], addr)

        elif entry.startswith('5'):
            list_directory(entry[1:], addr)

        elif entry.startswith('6'):
            theme_manager(entry[1:])

        elif entry.startswith('7'):
            history_search(entry[1:], addr)

        took = round(time.perf_counter() - init, 5)
        print('Took:', took)


os.makedirs(APP_HOME, exist_ok=True)

clients = []
cache = DirCache()
dispatcher = Dispatcher()
home = os.path.expanduser('~')

py_version = sys.version
py_version = py_version[:py_version.index(' ')]
py_not = 'Python' + ';' + py_version  # notation

exes_with_version = {}


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

for exe in exes_to_search:
    threading.Thread(target=get_version, args=(exe,)).start()
