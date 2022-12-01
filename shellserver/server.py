import socket

from .__init__ import PORT, APP_HOME, SEP

# Quit program as soon as possible
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('localhost', PORT))
except OSError:
    raise SystemExit

import sys
import os
import subprocess
import threading

from . import gitinfo
from .cache import DirCache
from .ls import Ls
from .style import style


def shell_manager(entry: str) -> None:
    if entry == 'Init':
        clients.append(1)

    elif entry == 'Exit':
        clients.pop()
        if not clients:
            cache.finish()
            # raising SystemExit would keep thread alive
            os._exit(0)

    elif entry == 'Kill':
        cache.finish()
        os._exit(0)


def zsearch(entry: str, addr: int) -> None:
    entry = entry.strip('.'+SEP).lower()
    result = cache.get(entry)
    sock.sendto(result.encode(), addr)


def fzfsearch(entry: str, addr: int) -> None:  # will receive two calls by 'pz'
    if not entry:  # if its the first
        result = '\n'.join([i[1] for i in cache.dirs])
        sock.sendto(result.encode(), addr)
    else:
        cache.update_by_full_path(entry)
        cache.sort()


def list_directory(entry: str, addr: int) -> None:
    entry = entry.removeprefix('Microsoft.PowerShell.Core\\FileSystem::')
    params = entry.split(';')
    ls = Ls(*params, to_cache=True)
    ls.echo(0)
    sock.sendto(ls.out.data.encode(), addr)


def scan(entry, addr):  # Basically, main
    no_error = int(entry[0])
    curdir, width, duration = entry[1:].split(';')
    width = int(width)
    duration = round(float(duration), 1)

    if curdir != home:
        cache.add(curdir)

    # Wsl
    curdir = curdir.removeprefix('Microsoft.PowerShell.Core\\FileSystem::')

    brackets = []
    after_brackets = []

    git_flag = False
    branch, status = gitinfo.gitinfo(curdir)
    if branch is not None:
        git_flag = True
        brackets.append(f'Branch;{branch}')
        if status is not None:
            brackets.append(f'Status;{status}')

    with os.scandir(curdir) as directory:
        for file in directory:
            if (py_not not in brackets
               and file.name.endswith(('.py', '.pyc', '.pyw', '.pyd'))):
                brackets.append(py_not)

            for exe in exes_with_version:
                if (exe + f';{exes_with_version[exe]}' not in brackets
                   and file.name.endswith(map_suffix[exe])):
                    brackets.append(
                        f'{map_lang_name[exe]};{exes_with_version[exe]}'
                    )

            for exe in exes_to_search:  # those who don't have version
                if (exe not in brackets
                   and file.name.endswith(map_suffix[exe])):
                    after_brackets.append(map_lang_name[exe])

    if home in curdir:
        curdir = '~' + curdir.removeprefix(home)

    stylized = style(
        curdir, git_flag, brackets, after_brackets, no_error, width, duration
    )

    sock.sendto(stylized.encode(), addr)


def mainloop():
    while 1:
        entry, addr = sock.recvfrom(4096)
        entry = entry.decode()

        if entry.startswith('%'):
            scan(entry[1:], addr)

        elif entry.startswith('#'):
            shell_manager(entry[1:])

        elif entry.startswith('!'):
            zsearch(entry[1:], addr)

        elif entry.startswith('*'):
            fzfsearch(entry[1:], addr)

        elif entry.startswith('@'):
            list_directory(entry[1:], addr)


def get_version(exe) -> None:
    try:
        out, err = subprocess.Popen(
            f'{exe} --version',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        ).communicate()
    except FileNotFoundError:
        return  # noqa

    if err:
        return  # noqa

    if exe in ('g++', 'gcc'):
        out = out.splitlines()[0]
        out = out[out.rindex(b')')+2:]
        exes_with_version.update({exe: out.strip().decode()})
        exes_to_search.remove(exe)
    elif exe == 'node':
        exes_with_version.update({exe: out.strip().decode()})
        exes_to_search.remove(exe)


os.makedirs(APP_HOME, exist_ok=True)

clients = []
cache = DirCache()
home = os.path.expanduser('~')

py_version = sys.version
py_version = py_version[:py_version.index(' ')]
py_not = 'Python' + ';' + py_version  # notation

exes_to_search = ['node', 'g++', 'gcc', 'lua']
exes_with_version = {}

map_suffix = {
    'node': '.js',
    'g++': '.cpp',
    'gcc': '.c',
    'lua': '.lua'
}
map_lang_name = {
    'node': 'Node',
    'g++': 'Cpp',
    'gcc': 'C',
    'lua': 'Lua'
}

for exe in exes_to_search:
    threading.Thread(target=get_version, args=(exe,)).start()

mainloop()
